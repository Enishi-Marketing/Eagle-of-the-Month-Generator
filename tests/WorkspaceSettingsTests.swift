import Foundation

@main
struct WorkspaceSettingsTests {
    static func main() throws {
        let manager = FileManager.default
        let temporary = manager.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? manager.removeItem(at: temporary) }
        let original = temporary.appendingPathComponent("missing parent/original workspace")
        try WorkspaceSettings.saveSheet(" https://docs.google.com/spreadsheets/u/0/d/example_ID/edit?usp=sharing ", tab: " Awards ", in: original)
        var config = try WorkspaceSettings.load(from: original)
        precondition(config["sheet_name"] as? String == "Awards")
        for folder in ["Photos", "Spreadsheet", "Output"] {
            precondition(manager.fileExists(atPath: original.appendingPathComponent(folder).path))
        }
        config["unrelated_setting"] = true
        let configURL = original.appendingPathComponent("config.json")
        try JSONSerialization.data(withJSONObject: config).write(to: configURL)
        let moved = temporary.appendingPathComponent("moved workspace")
        try manager.moveItem(at: original, to: moved)
        try WorkspaceSettings.saveSheet("another_ID", tab: "", in: moved)
        config = try WorkspaceSettings.load(from: moved)
        precondition(config["sheet_url"] as? String == "another_ID")
        precondition(config["unrelated_setting"] as? Bool == true)
        let localPhotos = moved.appendingPathComponent("Original Photos")
        try manager.createDirectory(at: localPhotos, withIntermediateDirectories: true)
        try WorkspaceSettings.savePhotoFolder(localPhotos, in: moved)
        config = try WorkspaceSettings.load(from: moved)
        precondition(config["photo_source_dir"] as? String == "Original Photos")
        precondition(config["sheet_url"] as? String == "another_ID")
        let relocated = temporary.appendingPathComponent("relocated workspace")
        try manager.moveItem(at: moved, to: relocated)
        let resolvedPhotos = try WorkspaceSettings.photoSource(in: relocated)
        precondition(resolvedPhotos.path == relocated.appendingPathComponent("Original Photos").path)
        try manager.moveItem(at: relocated, to: moved)
        let externalPhotos = temporary.appendingPathComponent("external photos")
        try manager.createDirectory(at: externalPhotos, withIntermediateDirectories: true)
        try WorkspaceSettings.savePhotoFolder(externalPhotos, in: moved)
        let externalSource = try WorkspaceSettings.photoSource(in: moved)
        precondition(externalSource.path == externalPhotos.path)
        let saved = try Data(contentsOf: moved.appendingPathComponent("config.json"))
        do {
            try WorkspaceSettings.saveSheet("https://example.com/not-a-sheet", tab: "", in: moved)
            fatalError("Invalid URL should be rejected")
        } catch { }
        let unchanged = try Data(contentsOf: moved.appendingPathComponent("config.json"))
        precondition(saved == unchanged)
        try Data("[]".utf8).write(to: moved.appendingPathComponent("config.json"))
        do {
            try WorkspaceSettings.saveSheet("another_ID", tab: "", in: moved)
            fatalError("Invalid config should be preserved and reported")
        } catch { }
        print("Workspace setup tests passed: missing folder, moved folder, saved settings, and invalid input.")
    }
}
