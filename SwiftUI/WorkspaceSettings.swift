import Foundation

struct WorkspaceSettings {
    static func prepare(_ root: URL) throws {
        for folder in ["Photos", "Spreadsheet", "Output"] {
            try FileManager.default.createDirectory(
                at: root.appendingPathComponent(folder, isDirectory: true),
                withIntermediateDirectories: true
            )
        }
    }

    static func saveSheet(_ value: String, tab: String, in root: URL) throws {
        let value = value.trimmingCharacters(in: .whitespacesAndNewlines)
        let pattern = "^(https://docs\\.google\\.com/spreadsheets/(?:u/[0-9]+/)?d/[A-Za-z0-9_-]+(?:[/?#].*)?|[A-Za-z0-9_-]+)$"
        guard value.range(of: pattern, options: .regularExpression) != nil else {
            throw NSError(domain: "Eagle", code: 1, userInfo: [NSLocalizedDescriptionKey: "Enter a Google Sheets URL or spreadsheet ID."])
        }
        let destination = root.appendingPathComponent("config.json")
        var config = try load(from: root)
        config["sheet_url"] = value
        config["sheet_name"] = tab.trimmingCharacters(in: .whitespacesAndNewlines)
        let data = try JSONSerialization.data(withJSONObject: config, options: [.prettyPrinted, .sortedKeys])
        try prepare(root)
        try data.write(to: destination, options: .atomic)
    }

    static func photoSource(in root: URL) throws -> URL {
        let config = try load(from: root)
        guard let value = config["photo_source_dir"] as? String, !value.isEmpty else {
            return root.appendingPathComponent("Photos", isDirectory: true)
        }
        let path = (value as NSString).expandingTildeInPath
        return path.hasPrefix("/") ? URL(fileURLWithPath: path, isDirectory: true)
            : root.appendingPathComponent(path, isDirectory: true)
    }

    static func savePhotoFolder(_ folder: URL, in root: URL) throws {
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: folder.path, isDirectory: &isDirectory), isDirectory.boolValue else {
            throw NSError(domain: "Eagle", code: 1, userInfo: [NSLocalizedDescriptionKey: "Choose an available photo folder. If it is in Google Drive, check that Drive is connected."])
        }
        var config = try load(from: root)
        let path = folder.standardizedFileURL.path
        let prefix = root.standardizedFileURL.path + "/"
        // A folder inside the workspace keeps working when the workspace moves.
        config["photo_source_dir"] = path.hasPrefix(prefix) ? String(path.dropFirst(prefix.count)) : path
        let data = try JSONSerialization.data(withJSONObject: config, options: [.prettyPrinted, .sortedKeys])
        try prepare(root)
        try data.write(to: root.appendingPathComponent("config.json"), options: .atomic)
    }

    static func load(from root: URL) throws -> [String: Any] {
        let source = root.appendingPathComponent("config.json")
        guard FileManager.default.fileExists(atPath: source.path) else { return [:] }
        let data = try Data(contentsOf: source)
        guard let config = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw NSError(domain: "Eagle", code: 1, userInfo: [NSLocalizedDescriptionKey: "config.json must contain a JSON object."])
        }
        return config
    }
}
