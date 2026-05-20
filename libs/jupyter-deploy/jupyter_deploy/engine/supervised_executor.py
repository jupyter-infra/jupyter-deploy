"""Base class for supervised command execution with progress tracking."""

import subprocess
from pathlib import Path
from typing import IO

from jupyter_deploy.engine.supervised_execution import ExecutionProgress
from jupyter_deploy.engine.supervised_execution_callback import ExecutionCallbackInterface
from jupyter_deploy.engine.supervised_phase import SupervisedDefaultPhase, SupervisedPhase
from jupyter_deploy.prompt_handler import PromptHandler


class SupervisedExecutor:
    """Execution and progress handler for a sequence of events in Jupyter-deploy command.

    On successful completion of the underlying command, the SupervisedExecutor
    grants its full reward. On failure (non-zero retcode), it communicates the
    error message and return code.

    To calculate intermediate rewards, a SupervisedExecutor tracks a sequence
    of declared phases (SupervisedPhase) - which may be empty - and
    a single default phase (SupervisedDefaultPhase).

    At any point, a phase MUST be active; either a SupervisedPhase or
    the SupervisedDefaultPhase. The SupervisedExecutor delegates to the active
    phase the task of calculating the incremental reward.

    Furthermore, the SupervisedExecutor handles:
    - Streaming command output line by line
    - Writing output to log files
    - Emitting progress updates via callback
    """

    def __init__(
        self,
        exec_dir: Path,
        log_file: Path,
        execution_callback: ExecutionCallbackInterface,
        default_phase: SupervisedDefaultPhase,
        phases: list[SupervisedPhase] | None = None,
        start_reward: float = 0.0,
        end_reward: float = 100.0,
        prompt_check_chars: str = ":?",
    ):
        """Initialize the executor.

        Args:
            exec_dir: Working directory for command execution
            log_file: Path where logs should be written
            execution_callback: Callback for execution events (progress, logs)
            default_phase: Default phase instance for progress tracking when not in declared phases
            phases: Optional explicitly declared phases
            start_reward: Accumulated reward (0-100) from previous sub-command executions of the
                jupyter-deploy command. Corresponds to the sum of all preceding SupervisedExecutors
                rewards.
            end_reward: Reward on successful completion of the SupervisedExecutor (0-100).
            prompt_check_chars: Specific chars of stdout that trigger prompt regex evaluation.
                (default: ":?")
        """
        if not phases:
            phases = []

        self.exec_dir = exec_dir
        self.log_file = log_file
        self._execution_callback = execution_callback
        self._should_parse_progress = execution_callback.should_parse_progress()
        self._log_handle: IO[str] | None = None
        self.prompt_check_chars = prompt_check_chars

        # Reward calculation
        self.end_reward = end_reward
        self._accumulated_reward = start_reward

        # Initialize declared phases as objects
        self._default_phase = default_phase
        self._declared_phases = phases

        # Track active phase (None = in default phase)
        self._active_declared_phase: SupervisedPhase | None = None
        self._next_declared_phase_index: int = 0  # Index of next phase to check
        self._next_declared_phase: SupervisedPhase | None = self._declared_phases[0] if self._declared_phases else None

        # Helper
        self._last_log_line = ""

    def execute(self, command: list[str]) -> int:
        """Execute a command and track progress, return command retcode.

        Manages the file handle where it will write logs.
        """
        self._current_command = command

        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Open log file for appending (handler may call execute() multiple times)
        with open(self.log_file, "a") as log_handle:
            self._log_handle = log_handle
            retcode = self._handle_execute_command(command)
            self._log_handle = None

        return retcode

    def _handle_execute_command(self, cmd: list[str]) -> int:
        """Execute a single command and stream its output, return retcode."""
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,  # Pipe stdin for prompt coordination
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # Keep stderr separate to prevent jumbling
            cwd=self.exec_dir,
            text=True,
            bufsize=0,  # Unbuffered for character-by-character reading
        )

        # Handle stdout+stdin with prompt detection and coordination
        if process.stdout and process.stdin:
            self._handle_io_with_prompt_detection(process)

        # Wait for process to complete
        retcode = process.wait()

        if retcode == 0:
            # Happy case: complete any remaining progress
            self._complete_execution()
        else:
            # Something went wrong: delegate to the execution callback
            # the job of displaying the right error message.
            self._execution_callback.on_execution_error(retcode)

        return retcode

    def _handle_io_with_prompt_detection(self, process: subprocess.Popen) -> None:
        """Handle subprocess I/O with prompt detection and stdin coordination.

        Uses PromptHandler to manage stdout reading, stdin piping, and coordination
        between them via event signaling.

        Args:
            process: The subprocess to manage I/O for
        """

        def is_prompt(buffer: str) -> bool:
            """Check if buffer looks like a prompt."""
            stripped = buffer.rstrip()
            return self._execution_callback.is_requesting_user_input(stripped)

        def on_line(line: str) -> None:
            """Handle a complete line."""
            self._process_line(line)

        def on_prompt(prompt: str) -> None:
            """Handle a detected prompt."""
            # Treat prompt as a line - _process_line will route to handle_interaction
            self._process_line(prompt)

        def on_stderr(stderr_lines: list[str]) -> None:
            """Handle buffered stderr lines after stdout completes."""
            for line in stderr_lines:
                # Write to log file
                self._write_to_log(line)
                # Process as normal log line (adds to buffer, emits to callback)
                stripped_line = line.rstrip("\n")
                self._last_log_line = stripped_line
                self._execution_callback.on_log_line(stripped_line)

        handler = PromptHandler(
            process=process,
            on_line=on_line,
            is_prompt=is_prompt,
            on_prompt=on_prompt,
            on_char=None,  # No character echo (handled by callback)
            on_stderr=on_stderr,
            buffer_size=200,  # Match the callback buffer size
            prompt_check_chars=self.prompt_check_chars,
        )
        handler.start()

    def _process_line(self, line: str) -> None:
        """Process a complete line of output.

        The complete line (may or may not have trailing newline)
        """
        # Write to log file (ensure newline)
        log_line = line if line.endswith("\n") else line + "\n"
        self._write_to_log(log_line)

        # Track last log line (used for progress updates)
        stripped_line = line.rstrip("\n")
        self._last_log_line = stripped_line

        # Check if we're in an interaction or this line starts one
        if self._execution_callback.is_waiting_for_interaction() or self._execution_callback.is_requesting_user_input(
            stripped_line
        ):
            # Handle interaction line (adds to context buffer only, not display buffer)
            self._execution_callback.handle_interaction(stripped_line)
            # Skip phase detection during interactive prompts
            return

        # Normal log line: emit to callback (handles buffering, display, and printing)
        self._execution_callback.on_log_line(stripped_line)

        # Parse the line for progress tracking (only if callback needs it)
        if self._should_parse_progress:
            self._parse_output_line(stripped_line)

    def _write_to_log(self, line: str) -> None:
        """Write a line to the log file.

        Args:
            line: The line to write (should include newline)
        """
        if self._log_handle:
            self._log_handle.write(line)
            self._log_handle.flush()

    def _emit_progress(self, progress: ExecutionProgress) -> None:
        """Emit a progress update via the callback."""
        self._execution_callback.on_progress(progress)

    def _parse_output_line(self, line: str) -> None:
        """Parse an output line and emit progress updates.

        Implements the state machine for phase transitions.

        Args:
            line: A single line of output (without trailing newline)
        """
        if self._active_declared_phase:
            # Case 1: A declared phase is active
            # 1.1: Check for exit
            if self._active_declared_phase.evaluate_exit(line):
                # Complete this phase, move to next declared phase, activate default
                full_phase_reward = self._active_declared_phase.complete()
                self._accumulated_reward += full_phase_reward
                self._active_declared_phase = None
                self._next_declared_phase_index += 1
                self._next_declared_phase = (
                    self._declared_phases[self._next_declared_phase_index]
                    if self._next_declared_phase_index < len(self._declared_phases)
                    else None
                )
                self._emit_current_progress()
                return

            # 1.2: Check for next subphase
            if self._active_declared_phase.evaluate_next_subphase(line):
                # Sub-phase transition - emit progress, keep phase active
                subphase_reward = self._active_declared_phase.complete_subphase()
                self._accumulated_reward += subphase_reward
                self._emit_current_progress()
                return

            # 1.3: Check for progress event
            if self._active_declared_phase.evaluate_progress(line):
                # Incremental event detected - emit progress, keep phase active
                progress_reward = self._active_declared_phase.complete_progress_event()
                self._accumulated_reward += progress_reward
                self._emit_current_progress()
                return

        else:
            # Case 2: No declared phase is active (in default phase)
            # 2.1: Check if any remaining declared phase can be entered (phase-skip)
            for i in range(self._next_declared_phase_index, len(self._declared_phases)):
                phase = self._declared_phases[i]
                if phase.evaluate_enter(line):
                    self._active_declared_phase = phase
                    self._next_declared_phase_index = i
                    self._next_declared_phase = phase
                    self._emit_current_progress()
                    return

            # 2.2: Otherwise evaluate default phase progress
            if self._default_phase.evaluate_progress(line):
                progress_reward = self._default_phase.complete_progress_event()
                self._accumulated_reward += progress_reward
                self._emit_current_progress()
                return

    def _complete_execution(self) -> None:
        """Complete execution and emit 100% progress for this command."""
        # Use last active phase label, or default phase label if none
        label = self._active_declared_phase.label if self._active_declared_phase else self._default_phase.label

        progress = ExecutionProgress(
            label=label,
            reward=self.end_reward,
        )
        self._emit_progress(progress)

    def _emit_current_progress(self) -> None:
        """Emit a progress update based on current execution state."""
        # Get label and capped percentage
        label = self._active_declared_phase.label if self._active_declared_phase else self._default_phase.label

        # Cap reward at end_reward - 1 to ensure we never reach 100% until subprocess completes
        # This prevents the progress bar from reaching 100% when event estimates are incorrect
        capped_reward = min(self._accumulated_reward, self.end_reward - 1)

        # Emit progress
        progress = ExecutionProgress(
            label=label,
            reward=capped_reward,
        )
        self._emit_progress(progress)
