# Eagle of the Month

A native macOS application for previewing, adjusting, exporting, and printing A4 award certificates. Requires macOS 15 or newer on Apple Silicon (the bundled Python framework requires macOS 15).

## Use the app

Open `dist/Eagle of the Month.app` or copy it to Applications. On first launch choose the existing Eagle project folder containing `Photos` and `Spreadsheet`. The application remembers that folder. The Python engine, house backgrounds, fonts, logos, and banner are bundled; Terminal and Python are not needed to use a packaged app.

Your photos, spreadsheet, `config.json`, and service-account credentials stay in that folder. Nothing private is included in the release archive. New photos may require the background-removal model to download on first use.

## Move to another Mac

Transfer both the app and your **private workspace folder** containing `config.json`,
`credentials.json`, `Spreadsheet`, and `Photos`. Keep this folder out of GitHub and
release archives. The workspace can have a different name or location on the new Mac.
On launch, choose that folder if prompted; you can also use **Choose Project Folder…**.
An app placed beside its workspace can discover that workspace automatically when
there is no valid remembered folder.

Use **Connect Google Sheet…** to save the sheet URL and optional tab name in the
workspace. Use **Import Sheet Credentials…** to copy a Google service-account JSON
key into the workspace as `credentials.json`. Share the sheet with that key's
`client_email` with Viewer access. Moving the workspace then preserves the connection;
you do not need to recreate the sheet or change its URL. Internet access and Google
Sheets API access are still required. The app reports connection errors without
silently switching to potentially outdated CSV data.

Existing service-account JSON files in the workspace are also discovered automatically.
The shared `~/.config/gsheets/credentials.json` location remains a fallback for older
setups, but its key must be transferred or imported when changing computers.
Photo lookup now defaults to the workspace's `Photos` folder; command-line users
can choose a separate source with `--photo-source-dir`.

## Build

Install `requirements.txt` and `requirements-build.txt` in `.venv`, then run `scripts/build_macos_app.sh`. The script fetches Sparkle 2.10.0 if needed; set `SPARKLE_ROOT` to reuse an existing distribution. The existing `.command` launcher opens the packaged application and passes this project folder.

## Release an update through GitHub

The app checks the latest GitHub Release in the repository named in `RELEASE_REPOSITORY`. That repository and its release assets must be publicly readable for Sparkle to fetch them. The app also offers **Check for Updates…** in its menu.

Release from an Apple Silicon Mac with macOS 15 or later, Xcode Command Line Tools, the Python build environment above, and GitHub CLI (`gh`). The publish script uses your GitHub CLI login or Git's existing credential helper. Use the original Sparkle private signing key in the macOS Keychain account `jp.ac.enishi.eagle-preview` so existing installations can verify the update.

1. Start from up-to-date `main`. Increase `VERSION` above the latest published version and update `RELEASE_NOTES.md`.
2. From the repository root, build the app and prepare the release assets.

   ```sh
   scripts/build_macos_app.sh
   scripts/prepare_github_release.sh
   ```

3. Test the app in `dist`. The preparation script audits the app bundle and ZIP. Before committing or pushing, audit the tracked source and review what is staged. Keep student photos, spreadsheets, generated PDFs, workspace config, and credentials local.

   ```sh
   .venv/bin/python scripts/audit_private_data.py
   git diff --cached --name-only
   ```

4. Commit the release changes, then tag and push that commit. Publish the prepared ZIP, SHA-256 checksum, and signed `appcast.xml` from `.build/github-release/<version>/`.

   ```sh
   version="$(tr -d '[:space:]' < VERSION)"
   git tag "v$version"
   git push --atomic origin main "refs/tags/v$version"
   scripts/publish_github_release.sh
   ```

5. Check that GitHub serves the new release as **Latest** and lists all three assets.

   ```sh
   .venv/bin/python scripts/github_cli.py release view --repo "$(cat RELEASE_REPOSITORY)"
   ```

   On a Mac running the previous version, choose **Check for Updates…** to test the upgrade.

Keep the generated asset names and appcast contents intact. The feed signature covers the URLs that Sparkle uses to download the update.

Local builds use ad hoc code signing, like the reference apps. Set `CODESIGN_IDENTITY` for a Developer ID build and notarize it before public distribution if that credential is available.
