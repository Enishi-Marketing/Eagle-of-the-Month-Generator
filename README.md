# Eagle of the Month

A native macOS application for previewing, adjusting, exporting, and printing A4 award certificates. Requires macOS 15 or newer on Apple Silicon (the bundled Python framework requires macOS 15).

## Use the app

Open `dist/Eagle of the Month.app` or copy it to Applications. On first launch choose the existing Eagle project folder containing `Photos` and `Spreadsheet`. The application remembers that folder. The Python engine, house backgrounds, fonts, logos, and banner are bundled; Terminal and Python are not needed to use a packaged app.

Your photos, spreadsheet, `config.json`, and service-account credentials stay in that folder. Nothing private is included in the release archive. New photos may require the background-removal model to download on first use.

## Build

Install `requirements.txt` and `requirements-build.txt` in `.venv`, then run `scripts/build_macos_app.sh`. The script fetches Sparkle 2.10.0 if needed; set `SPARKLE_ROOT` to reuse an existing distribution. The existing `.command` launcher opens the packaged application and passes this project folder.

## Automatic updates and GitHub Releases

Set `RELEASE_REPOSITORY` to the chosen GitHub `owner/repository`, or save that value in a file named `RELEASE_REPOSITORY`. Build with that setting to embed the GitHub latest-release appcast URL. Builds without a repository are local builds with updates inactive.

The application checks automatically and includes **Check for Updates…** in its menu. Both update archives and feeds are Ed25519 signed. The private signing key lives in the macOS Keychain account `jp.ac.enishi.eagle-preview`; only the public key is shipped. Generate that account once using Sparkle's `bin/generate_keys --account jp.ac.enishi.eagle-preview` before creating your first release. Preserve the signing key for all future releases.

For each release:

1. Increment `VERSION` and update `RELEASE_NOTES.md`.
2. Run `scripts/build_macos_app.sh`.
3. Run `scripts/prepare_github_release.sh` to create the ZIP, checksum, and signed appcast.
4. Run `scripts/publish_github_release.sh` with GitHub CLI. The helper uses your CLI login or Git's existing GitHub credential helper without printing or saving credentials. You can also upload those three files to a GitHub Release tagged `v<VERSION>`.

GitHub release asset names contain dots rather than spaces so the signed feed URLs exactly match uploaded names. Do not edit a generated appcast: changes invalidate its signature.

Local builds use ad hoc code signing, like the reference apps. Set `CODESIGN_IDENTITY` for a Developer ID build and notarize it before public distribution if that credential is available.
