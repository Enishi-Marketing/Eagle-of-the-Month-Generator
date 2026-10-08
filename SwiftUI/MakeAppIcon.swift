import AppKit

// Native vector artwork: golden eagle wings and an award star on navy.
let output = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
let gold = NSColor(calibratedRed: 0.98, green: 0.76, blue: 0.27, alpha: 1)
let cream = NSColor(calibratedRed: 1, green: 0.95, blue: 0.80, alpha: 1)

func polygon(_ points: [(CGFloat, CGFloat)], color: NSColor) {
    let path = NSBezierPath()
    path.move(to: NSPoint(x: points[0].0, y: points[0].1))
    for point in points.dropFirst() { path.line(to: NSPoint(x: point.0, y: point.1)) }
    path.close()
    color.setFill()
    path.fill()
}

for size in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let pixels = size * scale
        let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels,
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
            colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
        let transform = AffineTransform(scale: CGFloat(pixels) / 1024)
        (transform as NSAffineTransform).concat()
        NSColor(calibratedRed: 0.06, green: 0.16, blue: 0.27, alpha: 1).setFill()
        NSBezierPath(roundedRect: NSRect(x: 32, y: 32, width: 960, height: 960), xRadius: 210, yRadius: 210).fill()
        polygon([(512, 462), (421, 595), (155, 744), (215, 585), (364, 518),
                 (235, 530), (297, 423), (420, 398), (512, 345)], color: gold)
        polygon([(512, 462), (603, 595), (869, 744), (809, 585), (660, 518),
                 (789, 530), (727, 423), (604, 398), (512, 345)], color: gold)
        polygon([(454, 460), (478, 680), (539, 702), (604, 642), (548, 625),
                 (562, 460), (512, 405)], color: cream)
        polygon([(512, 355), (535, 307), (590, 300), (551, 261), (560, 208),
                 (512, 233), (464, 208), (473, 261), (434, 300), (489, 307)], color: gold)
        NSGraphicsContext.restoreGraphicsState()
        let name = "icon_\(size)x\(size)\(scale == 2 ? "@2x" : "").png"
        try bitmap.representation(using: .png, properties: [:])!.write(to: output.appendingPathComponent(name))
    }
}
