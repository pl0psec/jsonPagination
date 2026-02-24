# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-24

### Breaking Changes
- **Minimum Python version is now 3.10+** (previously 3.7+)
  - Required for modern type hint syntax (PEP 604)
  - If you need Python 3.7-3.9 support, use version 0.4.0

### Changed
- Updated all type hints to Python 3.10+ union syntax
  - `Optional[str]` → `str | None`
  - `Dict[str, Any]` → `dict[str, Any]`
  - `List[Any]` → `list[Any]`
- Updated CI to test Python 3.10, 3.11, 3.12, 3.13
- Removed unused import (`collections.abc.Callable`)
- Improved type hint readability throughout codebase

### Benefits
- **Performance**: Python 3.11+ provides 10-30% speedup for pagination workloads
- **Maintainability**: Cleaner, more readable type hints
- **Modern**: Uses latest Python best practices (PEP 604)
- **Future-proof**: Ready for upcoming Python versions

### Migration Guide
If upgrading from 0.x:
1. Ensure you are using Python 3.10 or newer
2. No API changes required - all interfaces remain compatible
3. Reinstall: `pip install --upgrade jsonPagination`

If you must stay on Python 3.7-3.9:
```bash
pip install 'jsonPagination==0.4.0'
```

---

## [0.4.0] - 2024-XX-XX (Last Python 3.7+ compatible release)

### Features
- Support for Python 3.7-3.12
- All pagination features
- See previous releases for full history

---

[1.0.0]: https://github.com/pl0psec/jsonPagination/compare/v0.4.0...v1.0.0
[0.4.0]: https://github.com/pl0psec/jsonPagination/releases/tag/v0.4.0
