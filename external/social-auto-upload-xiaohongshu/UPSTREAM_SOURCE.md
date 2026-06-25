# Upstream Source

- Repository: https://github.com/dreammis/social-auto-upload
- Snapshot: main branch zip archive
- Observed HEAD: 70a58b739fb2871e86aec924269a98928974c71b
- Pulled on: 2026-06-25

This directory contains only the Xiaohongshu-related subset needed for local evaluation:

- `uploader/xiaohongshu_uploader`
- `uploader/xhs_uploader`
- shared runtime helpers required by the Xiaohongshu uploader
- Xiaohongshu skill docs, examples, media, and tests

The original all-platform CLI was not copied because it imports multiple non-Xiaohongshu uploaders at module import time.
