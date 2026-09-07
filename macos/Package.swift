// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "InterlockingTiles",
    platforms: [.macOS(.v12)],
    targets: [
        .executableTarget(
            name: "InterlockingTiles",
            path: "Sources/InterlockingTiles"
        )
    ]
)
