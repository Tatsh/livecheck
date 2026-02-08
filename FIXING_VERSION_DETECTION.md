# Fixing Version Detection Issues

This document explains how to fix version detection issues for packages in tatsh-overlay.

## Fixed Issues

### Libretro Packages (✅ Fixed)

**Affected packages:**
- `games-emulation/fuse-libretro`
- `games-emulation/pcsx-rearmed-libretro`

**Problem:** These packages use slash-based tags like `1/1/1` or `12/31/2023`.

**Solution:** Use the `handle_libretro` transformation function which converts slashes to dots.

**Usage in `livecheck.json`:**
```json
{
  "transformation_function": "handle_libretro"
}
```

## Remaining Issues

The following packages need investigation and fixes:

### App Emulation Packages

1. **`app-emulation/basiliskii`**
   - Needs investigation of upstream tagging scheme
   - Likely requires custom transformation function

2. **`app-emulation/sheepshaver`**
   - Needs investigation of upstream tagging scheme
   - Likely requires custom transformation function

### Development Packages

3. **`dev-db/prisma-engines`**
   - May need regex-based version extraction
   - Check if tags include prefixes that need stripping

4. **`dev-python/thinc`**
   - Check PyPI versioning vs GitHub tags
   - May need `stable_version` regex to filter pre-releases

5. **`dev-qt/qtwebkit`**
   - Likely has complex versioning scheme
   - May need custom transformation or regex pattern

### Games Packages

6. **`games-arcade/stepmania`**
   - Check if version tags include prefixes
   - May need transformation to normalize versions

7. **`games-emulation/cemu`**
   - Investigate tag format (likely date-based or custom)
   - May need custom handler similar to `handle_outfox`

8. **`games-emulation/mupen64plus-video-gliden64`**
   - Check if tags match plugin versioning scheme
   - May need regex or transformation

9. **`games-emulation/rpcs3`**
   - Already has `prefix_v` in TAG_NAME_FUNCTIONS
   - If still inaccurate, check `stable_version` regex

### Media Packages

10. **`media-video/vapoursynth`**
    - Check release tag format
    - May need version normalization

## How to Fix

### Step 1: Investigate the Package

For each package, check:

1. **Upstream repository tags:**
   ```bash
   curl -s "https://api.github.com/repos/{owner}/{repo}/tags" | jq '.[].name' | head -20
   ```

2. **Current ebuild version:**
   Check the ebuild filename to see what version format is expected.

3. **Tag patterns:**
   Look for common patterns like:
   - Prefixes that need removal (`v`, `release-`, etc.)
   - Suffixes that cause issues (`-stable`, `-beta`, etc.)
   - Date formats that need conversion
   - Separators that need normalization (`_` to `.`, `/` to `.`)

### Step 2: Choose a Solution

Based on the investigation, use one of these approaches:

#### A. Use Existing Transformation Function

Add to `livecheck.json`:
```json
{
  "transformation_function": "handle_libretro"
}
```

Available functions:
- `dotize` - Convert dashes and underscores to dots
- `prefix_v` - Add `v` prefix
- `handle_libretro` - Convert slashes to dots
- `handle_outfox` - Handle Outfox pre-release versioning
- `handle_pl` - Handle `-pl\d+` suffixes
- `handle_cython_post_suffix` - Convert `.post` to `.`
- `handle_re` - Handle re3/reVC/reLCS prefixes

#### B. Use Regex Version Replacement

Add to `livecheck.json`:
```json
{
  "pattern_version": "^release-(.*)$",
  "replace_version": "\\1"
}
```

This allows removing prefixes, suffixes, or reformatting versions using regex.

#### C. Use Stable Version Filter

To filter out development versions:
```json
{
  "stable_version": "^\\d+\\.\\d+\\.\\d+$"
}
```

Only versions matching this regex will be considered.

#### D. Create New Transformation Function

If none of the above work, add a new function to `livecheck/special/handlers.py`:

```python
def handle_packagename(s: str) -> str:
    """Handle packagename versioning."""
    logger.debug('handle_packagename() <- "%s"', s)
    # Transform the version string
    ret = s.replace('something', 'otherthing')
    logger.debug('handle_packagename() -> "%s"', ret)
    return ret
```

Then add tests in `tests/special/test_handlers.py` and import in the module.

### Step 3: Test the Fix

1. Add the configuration to `livecheck.json` in tatsh-overlay
2. Run livecheck on the package:
   ```bash
   livecheck category/package-name
   ```
3. Verify the correct version is detected
4. Ensure the version can be used in an ebuild filename

### Step 4: Document

Update this file with:
- The problem identified
- The solution implemented
- Example usage

## Testing

To test a transformation function:

```python
from livecheck.special.handlers import handle_libretro

# Test the transformation
result = handle_libretro("1/1/1")
assert result == "1.1.1"
```

## Notes

- Transformation functions are loaded from either `livecheck.special.handlers` or `livecheck.utils`
- Functions should be idempotent (safe to call multiple times)
- Always add debug logging to transformation functions
- Test edge cases (empty strings, already-correct format, etc.)
- Keep transformation logic simple and focused
