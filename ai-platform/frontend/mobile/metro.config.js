const { getDefaultConfig } = require('expo/metro-config');
const { withNativeWind } = require('nativewind/metro');
const path = require('path');

const config = getDefaultConfig(__dirname);

// Block Metro from scanning Claude worktree directories —
// they contain stale files that conflict with the main project.
config.resolver.blockList = [
  /\.claude[/\\]worktrees[/\\].*/,
];

module.exports = withNativeWind(config, { input: './global.css' });
