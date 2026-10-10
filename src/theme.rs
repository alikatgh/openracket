use iced::widget::{button, container, text_editor};
use iced::{Background, Border, Color, Theme};
#[derive(Clone, Copy)]
pub struct Colors {
    pub background: Color,
    pub chrome: Color,
    pub panel: Color,
    pub border: Color,
    pub text: Color,
    pub muted: Color,
    pub accent: Color,
    pub accent_ink: Color,
    pub error: Color,
}
pub fn colors(theme: &Theme) -> Colors {
    let p = theme.palette();
    let dark = p.background.r < 0.5;
    if dark {
        Colors {
            background: c(0x121619),
            chrome: c(0x191e22),
            panel: c(0x151a1e),
            border: c(0x2b3339),
            text: c(0xe1e7e9),
            muted: c(0x99a6ad),
            accent: c(0x9bdbc2),
            accent_ink: c(0x172b23),
            error: c(0xf0a59c),
        }
    } else {
        Colors {
            background: c(0xfafbf9),
            chrome: c(0xf0f3ef),
            panel: c(0xf5f7f3),
            border: c(0xdbe2db),
            text: c(0x25312c),
            muted: c(0x59685f),
            accent: c(0x246e55),
            accent_ink: c(0xffffff),
            error: c(0xaf4035),
        }
    }
}
pub const fn c(hex: u32) -> Color {
    Color::from_rgb(
        ((hex >> 16) & 255) as f32 / 255.0,
        ((hex >> 8) & 255) as f32 / 255.0,
        (hex & 255) as f32 / 255.0,
    )
}
pub fn theme(dark: bool) -> Theme {
    Theme::custom(
        if dark {
            "OpenRacket Dark"
        } else {
            "OpenRacket Light"
        },
        iced::theme::Palette {
            background: if dark { c(0x121619) } else { c(0xfafbf9) },
            text: if dark { c(0xe1e7e9) } else { c(0x25312c) },
            primary: if dark { c(0x9bdbc2) } else { c(0x246e55) },
            success: c(0x78ba98),
            warning: c(0xd8b878),
            danger: c(0xe6948c),
        },
    )
}
pub fn surface(theme: &Theme) -> container::Style {
    let p = colors(theme);
    container::Style {
        background: Some(p.background.into()),
        text_color: Some(p.text),
        ..Default::default()
    }
}
pub fn chrome(theme: &Theme) -> container::Style {
    let p = colors(theme);
    container::Style {
        background: Some(p.chrome.into()),
        text_color: Some(p.text),
        border: Border {
            color: p.border,
            width: 1.0,
            radius: 0.into(),
        },
        ..Default::default()
    }
}
pub fn panel(theme: &Theme) -> container::Style {
    let p = colors(theme);
    container::Style {
        background: Some(p.panel.into()),
        text_color: Some(p.text),
        ..Default::default()
    }
}
pub fn card(theme: &Theme) -> container::Style {
    let p = colors(theme);
    container::Style {
        background: Some(p.chrome.into()),
        text_color: Some(p.text),
        border: Border {
            color: p.border,
            width: 1.0,
            radius: 12.into(),
        },
        ..Default::default()
    }
}
pub fn subtle(theme: &Theme, status: button::Status) -> button::Style {
    let p = colors(theme);
    let hover = matches!(status, button::Status::Hovered | button::Status::Pressed);
    button::Style {
        background: hover.then_some(Background::Color(p.border)),
        text_color: if matches!(status, button::Status::Disabled) {
            p.muted
        } else {
            p.text
        },
        border: Border {
            radius: 6.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}
pub fn primary(theme: &Theme, status: button::Status) -> button::Style {
    let p = colors(theme);
    button::Style {
        background: Some(
            if matches!(status, button::Status::Disabled) {
                p.border
            } else {
                p.accent
            }
            .into(),
        ),
        text_color: if matches!(status, button::Status::Disabled) {
            p.muted
        } else {
            p.accent_ink
        },
        border: Border {
            radius: 6.into(),
            ..Default::default()
        },
        ..Default::default()
    }
}
pub fn danger(theme: &Theme, status: button::Status) -> button::Style {
    let mut s = subtle(theme, status);
    s.text_color = colors(theme).error;
    s
}
pub fn editor(theme: &Theme, status: text_editor::Status) -> text_editor::Style {
    let p = colors(theme);
    text_editor::Style {
        background: p.background.into(),
        border: Border {
            color: if matches!(status, text_editor::Status::Focused { .. }) {
                p.border
            } else {
                p.background
            },
            width: 0.0,
            radius: 0.into(),
        },
        placeholder: p.muted,
        value: p.text,
        selection: Color {
            a: 0.25,
            ..p.accent
        },
    }
}

/// Keep every syntax token readable against the actual editor surface.
pub fn syntax_format(
    highlight: &iced::highlighter::Highlight,
    theme: &Theme,
) -> iced::advanced::text::highlighter::Format<iced::Font> {
    let mut format = highlight.to_format();
    let p = colors(theme);
    if let Some(color) = format.color {
        format.color = Some(ensure_contrast(color, p.background, 4.5));
    }
    if let Some(font) = &mut format.font {
        font.family = iced::font::Family::Name("Noto Sans Mono");
    }
    format
}
fn luminance(c: Color) -> f32 {
    fn channel(x: f32) -> f32 {
        if x <= 0.04045 {
            x / 12.92
        } else {
            ((x + 0.055) / 1.055).powf(2.4)
        }
    }
    0.2126 * channel(c.r) + 0.7152 * channel(c.g) + 0.0722 * channel(c.b)
}
fn contrast(a: Color, b: Color) -> f32 {
    let a = luminance(a);
    let b = luminance(b);
    (a.max(b) + 0.05) / (a.min(b) + 0.05)
}
fn ensure_contrast(mut color: Color, background: Color, minimum: f32) -> Color {
    color.a = 1.0;
    if contrast(color, background) >= minimum {
        return color;
    }
    let target = if luminance(background) < 0.5 {
        Color::WHITE
    } else {
        Color::BLACK
    };
    let original = color;
    let mut low = 0.0;
    let mut high = 1.0;
    for _ in 0..10 {
        let t = (low + high) / 2.0;
        let mixed = Color::from_rgb(
            original.r + (target.r - original.r) * t,
            original.g + (target.g - original.g) * t,
            original.b + (target.b - original.b) * t,
        );
        if contrast(mixed, background) >= minimum {
            high = t;
            color = mixed;
        } else {
            low = t;
        }
    }
    color
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn muted_chrome_text_meets_normal_text_contrast() {
        for dark in [false, true] {
            let p = colors(&theme(dark));
            for bg in [p.background, p.chrome, p.panel] {
                assert!(contrast(p.muted, bg) >= 4.5);
            }
        }
    }
    #[test]
    fn syntax_minimum_contrast_for_both_schemes() {
        for dark in [false, true] {
            let p = colors(&theme(dark));
            for color in [c(0x999988), c(0x65737e), c(0xbf616a), c(0xa3be8c)] {
                let result = ensure_contrast(color, p.background, 4.5);
                assert!(contrast(result, p.background) >= 4.499);
            }
        }
    }
}
