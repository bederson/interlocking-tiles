// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "TileConsole",
    platforms: [.macOS(.v12)],
    targets: [
        .executableTarget(
            name: "TileConsole",
            path: "Sources/TileConsole"
        )
    ]
)
