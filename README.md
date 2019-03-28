# JS Library Report 0.2.0

This script uses some heuristic to try determine the version of a js library and check their integrity using a CDN (Cloudflare) and generate an HTML report:
 - Compare files
 - Check latest version
 - Shows diff

### USAGE
 ```sh
 jslr.py <folder>
```
  - **folder** - The path where the script search for JS libraries

### KNOWN ISSUES
- It's not perfect. Have "false positives"
- Only support UTF-8 enconding
