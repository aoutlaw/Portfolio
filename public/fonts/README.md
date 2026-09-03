# Webfonts

Poppins (Regular / SemiBold / Bold), Gelasio and Yesteryear, as the exact
woff2 subsets the published Figma Sites build serves. Self-hosting them means
type renders identically to the live site with no third-party request — a
blocked or slow Google Fonts response used to drop the whole site onto a
system fallback, which reads noticeably tighter than Poppins at small sizes.

All three families are licensed under the SIL Open Font License 1.1.

The `@font-face` rules, including the unicode-range per subset, live in
`src/styles/fonts.css`.
