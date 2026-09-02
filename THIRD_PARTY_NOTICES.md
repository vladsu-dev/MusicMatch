# Third-party notices

MusicMatch contains or depends on third-party software. These components are
not relicensed by the MusicMatch proprietary license; their own licenses remain
in force.

## Yandex Music API

| Component | Value |
|---|---|
| Package | `yandex-music` |
| Upstream project | https://github.com/MarshalX/yandex-music-api |
| License | GNU LGPL v3.0 |
| Role in MusicMatch | Optional provider integration for reading a user's favorite artists |

MusicMatch imports `yandex_music` as a normal Python dependency. The project's
source code does not copy the library into this repository and does not modify
it in place.

The upstream project describes itself as an **unofficial** client for the
undocumented Yandex Music API. This is independent of the package's LGPL
license: an open-source license does not grant permission to use Yandex's
service outside the service's own terms. Review the applicable Yandex terms and
obtain legal/product approval before enabling this integration in a public or
commercial deployment.

### LGPL compliance notes

The GNU LGPL v3.0 permits an application to use the library under terms of its
choice, while imposing conditions on the library itself and on certain forms of
combined distribution. If MusicMatch is ever distributed together with a
modified copy of `yandex-music`, the modified library must retain the rights
required by LGPL-3.0. The application must also preserve the applicable notices
and rights needed for users to replace or relink the LGPL component.

For the official LGPL-3.0 text, see:
https://www.gnu.org/licenses/lgpl-3.0.html

Upstream license information:
https://github.com/MarshalX/yandex-music-api

## Dependency policy

When adding a new dependency:

1. Record the package and its license in this document.
2. Check whether the license is compatible with the proprietary MusicMatch
   distribution model.
3. Keep the dependency as a separate package where practical; do not copy
   third-party source into MusicMatch without reviewing its license first.
