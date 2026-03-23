package wizard

import (
	"github.com/charmbracelet/lipgloss"
)

// Brand colors.
var (
	ColorCyan    = lipgloss.Color("#00D4FF")
	ColorPurple  = lipgloss.Color("#A855F7")
	ColorRed     = lipgloss.Color("#EF4444")
	ColorGreen   = lipgloss.Color("#22C55E")
	ColorYellow  = lipgloss.Color("#EAB308")
	ColorGray    = lipgloss.Color("#6B7280")
	ColorWhite   = lipgloss.Color("#F9FAFB")
	ColorDim     = lipgloss.Color("#9CA3AF")
)

// Text styles.
var (
	TitleStyle = lipgloss.NewStyle().
			Foreground(ColorCyan).
			Bold(true)

	SubtitleStyle = lipgloss.NewStyle().
			Foreground(ColorDim)

	SuccessStyle = lipgloss.NewStyle().
			Foreground(ColorGreen)

	ErrorStyle = lipgloss.NewStyle().
			Foreground(ColorRed)

	WarningStyle = lipgloss.NewStyle().
			Foreground(ColorYellow)

	DimStyle = lipgloss.NewStyle().
			Foreground(ColorGray)

	BoldStyle = lipgloss.NewStyle().
			Bold(true)

	AccentStyle = lipgloss.NewStyle().
			Foreground(ColorPurple).
			Bold(true)
)

// Box styles.
var (
	BoxStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(ColorCyan).
			Padding(1, 2)

	SuccessBoxStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(ColorGreen).
			Padding(1, 2)

	ErrorBoxStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(ColorRed).
			Padding(1, 2)

	WarningBoxStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(ColorYellow).
			Padding(1, 2)

	SummaryBoxStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(ColorPurple).
			Padding(1, 2)
)

// Check/cross marks.
var (
	CheckMark   = SuccessStyle.Render("✓")
	CrossMark   = ErrorStyle.Render("✗")
	WarningMark = WarningStyle.Render("!")
	DotMark     = DimStyle.Render("◌")
	SkipMark    = DimStyle.Render("-")
)

// GORILLA ASCII ART (large version).
const GorillaASCII = `
                    ▄▄▄▄▄▄▄▄▄▄▄▄▄
                ▄█▀▀             ▀▀█▄
             ▄█▀                     ▀█▄
           ▄█▀                         ▀█▄
     ▄▄▄▄██     ▄▄▄▄▄       ▄▄▄▄▄     ██▄▄▄▄
   █▀    ██    █▀   ▀█     █▀   ▀█    ██    ▀█
  █      ██    █ ●   █     █   ● █    ██      █
   █▄    ██    ▀█▄▄▄█▀     ▀█▄▄▄█▀    ██    ▄█
     ▀▀▀▀██                             ██▀▀▀▀
          ██         ▄█████▄            ██
          ██        █▀     ▀█           ██
           █▄      █  ▀▀▀▀▀  █        ▄█
            ▀█▄     ▀█▄▄▄▄▄█▀      ▄█▀
              ▀█▄▄                ▄▄█▀
                 ▀▀█▄▄▄▄▄▄▄▄▄▄█▀▀
`

// GORILLA ASCII ART (small version for narrow terminals).
const GorillaASCIISmall = `
      ▄▄▄▄▄▄▄
    █▀       ▀█
   █  ●   ●   █
   █    ▄▄▄    █
    █▀ ▀▀▀▀▀ █
     ▀█▄▄▄▄█▀
`

// EMBEDINATOR text banner (large).
const EmbeddinatorBanner = `
 ███████╗███╗   ███╗██████╗ ███████╗██████╗ ██╗███╗   ██╗ █████╗ ████████╗ ██████╗ ██████╗
 ██╔════╝████╗ ████║██╔══██╗██╔════╝██╔══██╗██║████╗  ██║██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗
 █████╗  ██╔████╔██║██████╔╝█████╗  ██║  ██║██║██╔██╗ ██║███████║   ██║   ██║   ██║██████╔╝
 ██╔══╝  ██║╚██╔╝██║██╔══██╗██╔══╝  ██║  ██║██║██║╚██╗██║██╔══██║   ██║   ██║   ██║██╔══██╗
 ███████╗██║ ╚═╝ ██║██████╔╝███████╗██████╔╝██║██║ ╚████║██║  ██║   ██║   ╚██████╔╝██║  ██║
 ╚══════╝╚═╝     ╚═╝╚═════╝ ╚══════╝╚═════╝ ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
`

// EMBEDINATOR text banner (small for narrow terminals).
const EmbeddinatorBannerSmall = "E M B E D I N A T O R"
