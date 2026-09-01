// Command auth-sidecar is an app-agnostic Traefik ForwardAuth service that gates access
// to the local app (JupyterLab) with AWS-identity tokens.
//
// It validates the same `k8s-aws-v1.` presigned-STS-GetCallerIdentity token construct that
// EKS uses (as minted by `jd proxy connect-info`), enforcing the known footguns:
//
//   - the embedded URL host must be the pinned regional STS endpoint (SSRF belt),
//   - the action must be GetCallerIdentity and X-Amz-Expires must be bounded,
//   - the `x-k8s-aws-id` binding header must equal this deployment's id (cross-deployment
//     replay defense) — and is replayed to STS so the signature covers it,
//   - the principal returned by STS must be in this deployment's AWS account AND its IAM role
//     name (assumed-role caller) or user name (IAM-user caller) must be on the matching allowlist.
//     IAM names are unique per account regardless of path, so name + account identifies the caller.
//
// A positive result is cached (keyed by the token string) for a short TTL, so the steady
// state is ~1 STS call/minute regardless of request rate; the WebSocket firehose authenticates
// once on the upgrade and then costs zero STS calls.
//
// Interface (the whole contract — kept clean for later extraction to its own repo):
//
//	env DEPLOYMENT_ID        required binding id (x-k8s-aws-id)
//	env AWS_ACCOUNT_ID       required account the caller's principal must belong to
//	env ROLE_NAME_ALLOWLIST  comma-separated allowed IAM role names (assumed-role callers)
//	env USER_NAME_ALLOWLIST  comma-separated allowed IAM user names (IAM-user callers)
//	env AWS_REGION           region (used only to derive the default STS endpoint)
//	env STS_ENDPOINT         pinned STS endpoint (default https://sts.<region>.amazonaws.com)
//	GET /auth           ForwardAuth endpoint -> 200 (allow) / 401 (auth failure) / 403 (not
//	                    allowed) / 503 + Retry-After (STS transiently unavailable)
package main

import (
	"context"
	"encoding/base64"
	"encoding/xml"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	listenAddr        = ":4181"
	tokenPrefix       = "k8s-aws-v1."
	bindingHeader     = "x-k8s-aws-id"
	maxTokenExpirySec = 900
	cacheTTL          = 60 * time.Second
	stsCallTimeout    = 5 * time.Second
	stsRetryBackoff   = 200 * time.Millisecond
)

// transientError marks an STS failure that is not the caller's fault — a network error, a 429,
// or a 5xx. handleAuth maps it to 503 + Retry-After (not 401) so a running kernel's websocket
// retries through a brief STS blip instead of being torn down as an auth failure.
type transientError struct{ err error }

func (e *transientError) Error() string { return e.err.Error() }
func (e *transientError) Unwrap() error { return e.err }

type config struct {
	deploymentID string
	accountID    string
	roleNames    map[string]bool
	userNames    map[string]bool
	stsHost      string
}

func loadConfig() (*config, error) {
	deploymentID := os.Getenv("DEPLOYMENT_ID")
	if deploymentID == "" {
		return nil, fmt.Errorf("DEPLOYMENT_ID is required")
	}
	accountID := os.Getenv("AWS_ACCOUNT_ID")
	if accountID == "" {
		return nil, fmt.Errorf("AWS_ACCOUNT_ID is required")
	}

	endpoint := os.Getenv("STS_ENDPOINT")
	if endpoint == "" {
		region := os.Getenv("AWS_REGION")
		if region == "" {
			return nil, fmt.Errorf("either STS_ENDPOINT or AWS_REGION is required")
		}
		endpoint = fmt.Sprintf("https://sts.%s.amazonaws.com", region)
	}
	parsed, err := url.Parse(endpoint)
	if err != nil {
		return nil, fmt.Errorf("invalid STS_ENDPOINT: %w", err)
	}

	return &config{
		deploymentID: deploymentID,
		accountID:    accountID,
		roleNames:    csvSet(os.Getenv("ROLE_NAME_ALLOWLIST")),
		userNames:    csvSet(os.Getenv("USER_NAME_ALLOWLIST")),
		stsHost:      parsed.Host,
	}, nil
}

// csvSet splits a comma-separated env value into a set, dropping blanks.
func csvSet(raw string) map[string]bool {
	set := map[string]bool{}
	for v := range strings.SplitSeq(raw, ",") {
		if v = strings.TrimSpace(v); v != "" {
			set[v] = true
		}
	}
	return set
}

// parsePrincipal extracts (account, kind, name) from the ARN STS returns for the caller:
//
//	arn:aws:sts::<acct>:assumed-role/<RoleName>/<session>  -> (<acct>, "role", "<RoleName>")
//	arn:aws:iam::<acct>:user/<path...>/<UserName>          -> (<acct>, "user", "<UserName>")
//
// STS strips the IAM role path from an assumed-role ARN, and user ARNs carry the path as a prefix;
// either way we key on the bare name, which is unique per account regardless of path. Any other
// principal shape (root, federated-user, service principal) yields kind "" and is not authorized.
func parsePrincipal(arn string) (account, kind, name string) {
	parts := strings.Split(arn, ":") // arn:<partition>:<service>::<account>:<resource>
	if len(parts) != 6 {
		return "", "", ""
	}
	account = parts[4]
	resource := parts[5]
	switch parts[2] {
	case "sts":
		if rest, ok := strings.CutPrefix(resource, "assumed-role/"); ok {
			if roleName, _, ok := strings.Cut(rest, "/"); ok && roleName != "" {
				return account, "role", roleName
			}
		}
	case "iam":
		if rest, ok := strings.CutPrefix(resource, "user/"); ok {
			// user/<path...>/<name> — the bare name is the last segment.
			segs := strings.Split(rest, "/")
			if userName := segs[len(segs)-1]; userName != "" {
				return account, "user", userName
			}
		}
	}
	return "", "", ""
}

// allows reports whether STS's canonical caller principal is authorized: it must belong to this
// deployment's account, and its IAM role name (assumed-role caller) or user name (IAM-user caller)
// must be on the matching allowlist. No prefix/wildcard matching. Account scoping is essential —
// names are only unique within an account, so matching by name alone would authorize a same-named
// principal in a different account.
func (c *config) allows(arn string) bool {
	account, kind, name := parsePrincipal(arn)
	if account == "" || account != c.accountID {
		return false
	}
	switch kind {
	case "role":
		return c.roleNames[name]
	case "user":
		return c.userNames[name]
	}
	return false
}

// cache is a tiny TTL cache of positive auth results keyed by the token string.
type cache struct {
	mu      sync.Mutex
	entries map[string]cacheEntry
}

type cacheEntry struct {
	arn     string
	expires time.Time
}

// get returns the cached ARN for a token, treating an expired entry as a miss. A past-TTL entry
// is deleted here on read, so the caller then re-verifies against STS. TTL is the only
// invalidation — entries are never updated in place, so a revoked/expired AWS credential keeps
// working until at most cacheTTL elapses.
func (c *cache) get(token string) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	e, ok := c.entries[token]
	if !ok || time.Now().After(e.expires) {
		delete(c.entries, token)
		return "", false
	}
	return e.arn, true
}

// put caches a verified ARN under the full token string for cacheTTL. Keying on the exact token
// means a refreshed/re-minted token is a distinct key that always forces a fresh STS check. The
// client re-mints a token roughly every cacheTTL, so a rotated-away key would otherwise never be
// read again and never self-evict; to bound the map we sweep all expired entries on every write.
// Only ~1 token is live at a time, so this keeps the map to a handful of entries.
func (c *cache) put(token, arn string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	now := time.Now()
	for k, e := range c.entries {
		if now.After(e.expires) {
			delete(c.entries, k)
		}
	}
	c.entries[token] = cacheEntry{arn: arn, expires: now.Add(cacheTTL)}
}

type stsResponse struct {
	Arn string `xml:"GetCallerIdentityResult>Arn"`
}

type server struct {
	cfg   *config
	cache *cache
	http  *http.Client
}

// verify decodes the token, hard-checks it against the pinned STS endpoint, replays it with
// the binding header, and returns the caller ARN if STS accepts the signed request.
func (s *server) verify(ctx context.Context, bearer, binding string) (string, error) {
	if binding != s.cfg.deploymentID {
		return "", fmt.Errorf("binding header %q does not match this deployment", binding)
	}
	if !strings.HasPrefix(bearer, tokenPrefix) {
		return "", fmt.Errorf("token is missing the %q prefix", tokenPrefix)
	}

	// The token is not a bearer secret we validate ourselves — it is a SigV4-*presigned*
	// sts:GetCallerIdentity request URL. The client signed it with THEIR OWN AWS credentials
	// (which never leave their machine) and base64url-encoded the resulting URL. Decoding it
	// yields that URL, with the SigV4 material carried entirely in its query string
	// (X-Amz-Credential / -Date / -Expires / -SignedHeaders / -Signature). We hold no signing
	// key: verification is "replay the client's own signed request to STS and see if STS accepts
	// it," which proves the client possessed valid credentials for the ARN STS reports back.
	raw, err := base64.RawURLEncoding.DecodeString(strings.TrimPrefix(bearer, tokenPrefix))
	if err != nil {
		return "", fmt.Errorf("token is not valid base64url: %w", err)
	}
	presigned, err := url.Parse(string(raw))
	if err != nil {
		return "", fmt.Errorf("token does not decode to a URL: %w", err)
	}

	// SSRF belt: only ever replay to the pinned STS host, never the URL's own host.
	if !strings.EqualFold(presigned.Host, s.cfg.stsHost) {
		return "", fmt.Errorf("token host %q is not the pinned STS endpoint", presigned.Host)
	}
	q := presigned.Query()
	if q.Get("Action") != "GetCallerIdentity" {
		return "", fmt.Errorf("token action is not GetCallerIdentity")
	}
	if expiry, err := strconv.Atoi(q.Get("X-Amz-Expires")); err != nil || expiry <= 0 || expiry > maxTokenExpirySec {
		return "", fmt.Errorf("token X-Amz-Expires is missing or out of bounds")
	}

	// Replay the client's presigned request verbatim, but only ever to the pinned STS host we
	// checked above — never to the URL's own host. RequestURI() preserves the path + the entire
	// signed query string (the signature), so STS recomputes SigV4 over exactly what the client
	// signed and validates it against the client's secret; we never reconstruct the signature.
	replayURL := "https://" + s.cfg.stsHost + presigned.RequestURI()

	// One bounded retry on the transient class (network error / 429 / 5xx) so a brief STS blip
	// doesn't 401 a live session. A genuine rejection (bad signature/expiry/binding -> 4xx) is
	// returned immediately and never retried.
	var arn string
	for attempt := 0; ; attempt++ {
		arn, err = s.replayToSTS(ctx, replayURL, binding)
		if err == nil {
			return arn, nil
		}
		_, transient := errors.AsType[*transientError](err)
		if attempt >= 1 || !transient {
			return "", err
		}
		select {
		case <-ctx.Done():
			return "", err
		case <-time.After(stsRetryBackoff):
		}
	}
}

// replayToSTS issues one presigned-request replay to the pinned STS host and returns the caller ARN.
// Network failures and 429/5xx responses are wrapped in *transientError; a non-transient 4xx (STS
// rejecting the signature) is a plain error the caller surfaces as a 401.
func (s *server) replayToSTS(ctx context.Context, replayURL, binding string) (string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, replayURL, nil)
	if err != nil {
		return "", err
	}
	// x-k8s-aws-id is listed in the token's X-Amz-SignedHeaders, so its value is folded into the
	// signature. We must send back the exact value the client signed or STS's signature check
	// fails — which is exactly what makes a token minted for a different DEPLOYMENT_ID unusable
	// here (the binding == deploymentID guard at the top of verify enforces the value we replay).
	req.Header.Set(bindingHeader, binding)
	req.Header.Set("Accept", "application/xml")

	resp, err := s.http.Do(req)
	if err != nil {
		return "", &transientError{fmt.Errorf("STS replay failed: %w", err)}
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<16))
	if resp.StatusCode != http.StatusOK {
		err := fmt.Errorf("STS rejected the token (status %d)", resp.StatusCode)
		if resp.StatusCode == http.StatusTooManyRequests || resp.StatusCode >= 500 {
			return "", &transientError{err}
		}
		return "", err
	}

	// STS accepted the signature: the response carries the caller's canonical principal ARN
	// (e.g. an assumed-role ARN). That ARN — not the token — is what we authorize against the
	// allowlist. It is also what gets cached, so cache hits skip this whole STS round-trip.
	var parsed stsResponse
	if err := xml.Unmarshal(body, &parsed); err != nil || parsed.Arn == "" {
		return "", fmt.Errorf("could not parse ARN from STS response")
	}
	return parsed.Arn, nil
}

func (s *server) handleAuth(w http.ResponseWriter, r *http.Request) {
	bearer := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
	if bearer == "" {
		http.Error(w, "missing Authorization", http.StatusUnauthorized)
		return
	}
	binding := r.Header.Get(bindingHeader)

	// Fast path: a token we already verified this minute. Re-check the allowlist on every hit
	// rather than caching the allow/deny decision — the cache holds the verified ARN, so an
	// allowlist change takes effect immediately (on the next request) without a redeploy,
	// while still skipping the STS round-trip.
	if arn, ok := s.cache.get(bearer); ok {
		if s.cfg.allows(arn) {
			w.WriteHeader(http.StatusOK)
			return
		}
		http.Error(w, "identity not allowed", http.StatusForbidden)
		return
	}

	// Slow path: prove the token via STS. A bad signature / wrong binding / expired token is a
	// 401 (authentication failure); a valid identity that simply is not permitted is a 403; STS
	// being unreachable/throttled is a 503 + Retry-After (transient, not the caller's fault).
	ctx, cancel := context.WithTimeout(r.Context(), stsCallTimeout)
	defer cancel()
	arn, err := s.verify(ctx, bearer, binding)
	if err != nil {
		if _, ok := errors.AsType[*transientError](err); ok {
			log.Printf("auth unavailable: %v", err)
			w.Header().Set("Retry-After", "2")
			http.Error(w, "auth temporarily unavailable", http.StatusServiceUnavailable)
			return
		}
		log.Printf("auth denied: %v", err)
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	// Authorization: the caller's principal must be in this account and its role/user name on the
	// matching allowlist. No prefix/wildcard matching — see config.allows.
	if !s.cfg.allows(arn) {
		log.Printf("auth denied: ARN %q not on allowlist", arn)
		http.Error(w, "identity not allowed", http.StatusForbidden)
		return
	}
	// Only reached once verified AND allowed, so the cache holds solely positive ARNs; a later
	// allowlist removal is still caught by the per-hit re-check on the fast path above.
	s.cache.put(bearer, arn)
	w.WriteHeader(http.StatusOK)
}

func main() {
	healthcheck := flag.Bool("healthcheck", false, "probe the local server and exit")
	flag.Parse()
	if *healthcheck {
		resp, err := http.Get("http://localhost" + listenAddr + "/healthz")
		if err != nil || resp.StatusCode != http.StatusOK {
			os.Exit(1)
		}
		os.Exit(0)
	}

	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("configuration error: %v", err)
	}

	s := &server{
		cfg:   cfg,
		cache: &cache{entries: map[string]cacheEntry{}},
		http:  &http.Client{Timeout: stsCallTimeout},
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/auth", s.handleAuth)
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusOK) })

	log.Printf("auth-sidecar listening on %s (deployment %s, STS %s)", listenAddr, cfg.deploymentID, cfg.stsHost)
	srv := &http.Server{Addr: listenAddr, Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	log.Fatal(srv.ListenAndServe())
}
