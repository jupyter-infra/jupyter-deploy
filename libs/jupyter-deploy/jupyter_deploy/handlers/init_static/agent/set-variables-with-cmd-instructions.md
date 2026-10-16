Set variables via command
```bash
# Set the value of specific variables via command line
jd config --VAR-NAME-1 VARVALUE1 --VAR-NAME-2 VARVALUE2

# Boolean variables take no value: --VAR-NAME sets true, --no-VAR-NAME sets false
jd config --BOOL-VAR-NAME
jd config --no-BOOL-VAR-NAME

# Find details of the variables available for this template
jd config --help
```
