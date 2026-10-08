import AppKit
import Foundation
import PDFKit
import SwiftUI
import Sparkle

private struct LayoutSettings: Codable {
    var student_scale: Double
    var student_x: Double
    var student_y: Double
    var exposure: Double
    var text_scale: Double
    var text_y: Double
    var show_photos: Bool
    var show_logos: Bool
    var show_banner: Bool
}

private struct GeneratorResult {
    let status: Int32
    let output: String
}

@MainActor
final class PreviewModel: ObservableObject {
    @Published var projectRoot: URL

    @Published var month = "May"
    @Published var year = "2026"
    @Published var useLocalCSV = false
    @Published var studentScale = 1.0
    @Published var studentX = 0.0
    @Published var studentY = 0.0
    @Published var exposure = 0.0
    @Published var textScale = 1.0
    @Published var textY = 0.0
    @Published var showPhotos = true
    @Published var showLogos = true
    @Published var showBanner = true
    @Published var document: PDFDocument?
    @Published var isGenerating = false
    @Published var statusText = "Preparing preview…"
    @Published var errorText: String?

    private var refreshTask: Task<Void, Never>?
    private var generationID = UUID()
    private var currentPreviewURL: URL?

    init(projectRoot: URL) {
        self.projectRoot = projectRoot
        loadLatestLocalPeriod()
    }

    func chooseWorkspace() {
        let panel = NSOpenPanel()
        panel.title = "Choose your Eagle of the Month project folder"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        guard FileManager.default.fileExists(atPath: url.appendingPathComponent("Spreadsheet").path) else {
            errorText = "Choose the project folder containing Spreadsheet and Photos."
            return
        }
        projectRoot = url
        UserDefaults.standard.set(url.path, forKey: "workspacePath")
        loadLatestLocalPeriod()
        scheduleRefresh()
    }

    deinit {
        if let currentPreviewURL {
            try? FileManager.default.removeItem(at: currentPreviewURL)
        }
    }

    var pageSummary: String {
        guard let document else { return "No pages" }
        return "\(document.pageCount) sheet\(document.pageCount == 1 ? "" : "s")"
    }

    func scheduleRefresh() {
        refreshTask?.cancel()
        refreshTask = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(350))
            guard !Task.isCancelled else { return }
            await self?.refresh()
        }
    }

    func refresh() async {
        let cleanMonth = month.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanYear = year.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanMonth.isEmpty, !cleanYear.isEmpty else {
            errorText = "Enter both a month and year."
            return
        }

        let currentID = UUID()
        generationID = currentID
        isGenerating = true
        errorText = nil
        statusText = "Building preview…"

        let settings = LayoutSettings(
            student_scale: studentScale,
            student_x: studentX,
            student_y: studentY,
            exposure: exposure,
            text_scale: textScale,
            text_y: textY,
            show_photos: showPhotos,
            show_logos: showLogos,
            show_banner: showBanner
        )

        let root = projectRoot
        let destination = FileManager.default.temporaryDirectory
            .appendingPathComponent("eagle-preview-\(currentID.uuidString).pdf")
        let localCSV = useLocalCSV
        let result = await Task.detached(priority: .userInitiated) {
            Self.runGenerator(
                root: root,
                month: cleanMonth,
                year: cleanYear,
                output: destination,
                localCSV: localCSV,
                settings: settings
            )
        }.value

        guard generationID == currentID else {
            try? FileManager.default.removeItem(at: destination)
            return
        }
        isGenerating = false
        guard result.status == 0,
              FileManager.default.fileExists(atPath: destination.path),
              let freshDocument = PDFDocument(url: destination),
              freshDocument.pageCount > 0 else {
            document = nil
            errorText = result.output.isEmpty ? "The preview could not be generated." : result.output
            statusText = "Preview unavailable"
            return
        }

        document = freshDocument
        if let oldPreview = currentPreviewURL, oldPreview != destination {
            try? FileManager.default.removeItem(at: oldPreview)
        }
        currentPreviewURL = destination
        statusText = "Ready · \(pageSummary)"
    }

    func resetLayout() {
        studentScale = 1.0
        studentX = 0.0
        studentY = 0.0
        exposure = 0.0
        textScale = 1.0
        textY = 0.0
        showPhotos = true
        showLogos = true
        showBanner = true
        scheduleRefresh()
    }

    func exportPDF() {
        guard document != nil, let currentPreviewURL else { return }
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.pdf]
        panel.canCreateDirectories = true
        panel.nameFieldStringValue = "eagle_\(month)_\(year).pdf"
        guard panel.runModal() == .OK, let selectedURL = panel.url else { return }
        do {
            if FileManager.default.fileExists(atPath: selectedURL.path) {
                try FileManager.default.removeItem(at: selectedURL)
            }
            try FileManager.default.copyItem(at: currentPreviewURL, to: selectedURL)
            statusText = "Saved \(selectedURL.lastPathComponent)"
        } catch {
            errorText = "Could not save the PDF: \(error.localizedDescription)"
        }
    }

    func printPDF() {
        guard let document else { return }
        let operation = document.printOperation(
            for: NSPrintInfo.shared,
            scalingMode: .pageScaleToFit,
            autoRotate: true
        )
        operation?.run()
    }

    private func loadLatestLocalPeriod() {
        let csvURL = projectRoot.appendingPathComponent("Spreadsheet/Eagle of the Month.csv")
        guard let contents = try? String(contentsOf: csvURL, encoding: .utf8) else { return }
        let rows = contents.split(whereSeparator: \.isNewline)
        guard let last = rows.last else { return }
        let fields = last.split(separator: ",", omittingEmptySubsequences: false).map(String.init)
        guard fields.count >= 5 else { return }
        month = fields[fields.count - 2].trimmingCharacters(in: .whitespacesAndNewlines)
        year = fields[fields.count - 1].trimmingCharacters(in: .whitespacesAndNewlines)
    }

    nonisolated private static func runGenerator(
        root: URL,
        month: String,
        year: String,
        output: URL,
        localCSV: Bool,
        settings: LayoutSettings
    ) -> GeneratorResult {
        let encoder = JSONEncoder()
        guard let data = try? encoder.encode(settings),
              let settingsJSON = String(data: data, encoding: .utf8) else {
            return GeneratorResult(status: 1, output: "Could not encode layout settings.")
        }

        let venvPython = root.appendingPathComponent(".venv/bin/python")
        let python = FileManager.default.isExecutableFile(atPath: venvPython.path)
            ? venvPython
            : URL(fileURLWithPath: "/usr/bin/python3")
        let process = Process()
        let pipe = Pipe()
        process.currentDirectoryURL = root
        let bundledBackend = Bundle.main.resourceURL?.appendingPathComponent("backend/EagleBackend")
        let isBundled = bundledBackend.map { FileManager.default.isExecutableFile(atPath: $0.path) } ?? false
        process.executableURL = isBundled ? bundledBackend : python
        var environment = ProcessInfo.processInfo.environment
        environment["EAGLE_WORKSPACE"] = root.path
        process.environment = environment
        process.arguments = (isBundled ? [] : [root.appendingPathComponent("generate.py").path]) + [
            "--month", month,
            "--year", year,
            "--output", output.path,
            "--layout-json", settingsJSON,
            "--non-interactive"
        ] + (localCSV ? ["--local-csv"] : [])
        process.standardOutput = pipe
        process.standardError = pipe

        do {
            try process.run()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            process.waitUntilExit()
            return GeneratorResult(
                status: process.terminationStatus,
                output: String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            )
        } catch {
            return GeneratorResult(status: 1, output: error.localizedDescription)
        }
    }
}

struct PDFPreview: NSViewRepresentable {
    let document: PDFDocument?

    func makeNSView(context: Context) -> PDFView {
        let view = PDFView()
        view.autoScales = true
        view.displayMode = .singlePageContinuous
        view.displayDirection = .vertical
        view.displaysPageBreaks = true
        view.backgroundColor = .windowBackgroundColor
        return view
    }

    func updateNSView(_ view: PDFView, context: Context) {
        if view.document !== document {
            view.document = document
            view.autoScales = true
        }
    }
}

private struct LabeledSlider: View {
    let title: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let format: (Double) -> String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(title)
                Spacer()
                Text(format(value)).foregroundStyle(.secondary).monospacedDigit()
            }
            Slider(value: $value, in: range)
        }
    }
}

struct ContentView: View {
    @StateObject var model: PreviewModel

    var body: some View {
        NavigationSplitView {
            Form {
                Section("Sheets") {
                    Button("Choose Project Folder…") { model.chooseWorkspace() }
                    Text(model.projectRoot.lastPathComponent).font(.caption).foregroundStyle(.secondary)
                    TextField("Month", text: $model.month)
                    TextField("Year", text: $model.year)
                    Toggle("Use local CSV", isOn: $model.useLocalCSV)
                        .help("Off uses the Google Sheet configured in config.json")
                }

                Section("Student photo") {
                    Toggle("Show photos", isOn: $model.showPhotos)
                    LabeledSlider(title: "Size", value: $model.studentScale, range: 0.5...1.4) {
                        "\(Int($0 * 100))%"
                    }
                    LabeledSlider(title: "Left / right", value: $model.studentX, range: -0.25...0.25) {
                        String(format: "%+.0f%%", $0 * 100)
                    }
                    LabeledSlider(title: "Up / down", value: $model.studentY, range: -0.20...0.20) {
                        String(format: "%+.0f%%", $0 * 100)
                    }
                    LabeledSlider(title: "Exposure", value: $model.exposure, range: -2.0...2.0) {
                        String(format: "%+.1f EV", $0)
                    }
                }

                Section("Type & artwork") {
                    LabeledSlider(title: "Text size", value: $model.textScale, range: 0.7...1.35) {
                        "\(Int($0 * 100))%"
                    }
                    LabeledSlider(title: "Text up / down", value: $model.textY, range: -0.12...0.12) {
                        String(format: "%+.0f%%", $0 * 100)
                    }
                    Toggle("Show house logos", isOn: $model.showLogos)
                    Toggle("Show top banner", isOn: $model.showBanner)
                }

                Button("Reset Layout") { model.resetLayout() }
            }
            .formStyle(.grouped)
            .navigationSplitViewColumnWidth(min: 275, ideal: 310, max: 360)
            .onChange(of: model.month) { model.scheduleRefresh() }
            .onChange(of: model.year) { model.scheduleRefresh() }
            .onChange(of: model.useLocalCSV) { model.scheduleRefresh() }
            .onChange(of: model.studentScale) { model.scheduleRefresh() }
            .onChange(of: model.studentX) { model.scheduleRefresh() }
            .onChange(of: model.studentY) { model.scheduleRefresh() }
            .onChange(of: model.exposure) { model.scheduleRefresh() }
            .onChange(of: model.textScale) { model.scheduleRefresh() }
            .onChange(of: model.textY) { model.scheduleRefresh() }
            .onChange(of: model.showPhotos) { model.scheduleRefresh() }
            .onChange(of: model.showLogos) { model.scheduleRefresh() }
            .onChange(of: model.showBanner) { model.scheduleRefresh() }
        } detail: {
            ZStack {
                PDFPreview(document: model.document)
                if model.isGenerating {
                    ProgressView("Updating preview…")
                        .padding(18)
                        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                } else if let error = model.errorText {
                    ContentUnavailableView(
                        "Preview unavailable",
                        systemImage: "exclamationmark.triangle",
                        description: Text(error)
                    )
                    .padding(40)
                }
            }
            .navigationTitle("Eagle of the Month")
            .toolbar {
                ToolbarItemGroup {
                    Text(model.statusText).foregroundStyle(.secondary)
                    Button { Task { await model.refresh() } } label: {
                        Label("Refresh", systemImage: "arrow.clockwise")
                    }
                    .disabled(model.isGenerating)
                    Button { model.printPDF() } label: {
                        Label("Print", systemImage: "printer")
                    }
                    .disabled(model.document == nil || model.isGenerating)
                    Button { model.exportPDF() } label: {
                        Label("Make PDF", systemImage: "square.and.arrow.down")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(model.document == nil || model.isGenerating)
                }
            }
        }
        .frame(minWidth: 1000, minHeight: 700)
        .task {
            if !FileManager.default.fileExists(atPath: model.projectRoot.path) {
                model.chooseWorkspace()
            } else {
                await model.refresh()
            }
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var updaterController: SPUStandardUpdaterController?

    func checkForUpdates() {
        updaterController?.checkForUpdates(nil)
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApplication.shared.setActivationPolicy(.regular)
        NSApplication.shared.activate(ignoringOtherApps: true)
        if Bundle.main.object(forInfoDictionaryKey: "SUFeedURL") != nil {
            let controller = SPUStandardUpdaterController(
                startingUpdater: true, updaterDelegate: nil, userDriverDelegate: nil
            )
            updaterController = controller
            if controller.updater.automaticallyChecksForUpdates {
                controller.updater.checkForUpdatesInBackground()
            }
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        for window in sender.windows where window.canBecomeMain {
            if window.isMiniaturized { window.deminiaturize(nil) }
            window.makeKeyAndOrderFront(nil)
        }
        sender.activate(ignoringOtherApps: true)
        return true
    }
}

@main
struct EaglePreviewApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var model: PreviewModel

    init() {
        let arguments = CommandLine.arguments
        let root: URL
        if let marker = arguments.firstIndex(of: "--project-root"), arguments.indices.contains(marker + 1) {
            root = URL(fileURLWithPath: arguments[marker + 1], isDirectory: true)
            UserDefaults.standard.set(root.path, forKey: "workspacePath")
        } else if let path = UserDefaults.standard.string(forKey: "workspacePath") {
            root = URL(fileURLWithPath: path, isDirectory: true)
        } else {
            root = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("Documents/Eagle of the Month")
        }
        _model = StateObject(wrappedValue: PreviewModel(projectRoot: root))
    }

    var body: some Scene {
        Window("Eagle of the Month", id: "preview") {
            ContentView(model: model)
        }
        .commands {
            CommandGroup(replacing: .newItem) { }
            CommandGroup(after: .appInfo) {
                Button("Check for Updates…") { appDelegate.checkForUpdates() }
            }
        }
    }
}
