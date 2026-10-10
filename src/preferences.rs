//! Small, explicit settings saves. Source buffers and session paths never enter this file.

use serde::{Deserialize, Serialize};
use std::{
    env,
    ffi::OsString,
    fs::{self, File},
    io::{Read, Write},
    path::{Path, PathBuf},
};

const MAX_CONFIG_BYTES: u64 = 64 * 1024;
const MAX_RACKET_PATH_BYTES: usize = 4096;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Preferences {
    pub dark: bool,
    pub font_size: f32,
    pub racket_path: Option<String>,
    pub wrap: bool,
    pub sidebar: bool,
}

impl Default for Preferences {
    fn default() -> Self {
        Self {
            dark: true,
            font_size: 15.0,
            racket_path: None,
            wrap: false,
            sidebar: true,
        }
    }
}

impl Preferences {
    fn validate(&self) -> Result<(), String> {
        if !self.font_size.is_finite() || !(11.0..=24.0).contains(&self.font_size) {
            return Err("Font size must be between 11 and 24.".into());
        }
        if let Some(path) = &self.racket_path
            && (path.trim().is_empty()
                || path.len() > MAX_RACKET_PATH_BYTES
                || path.chars().any(char::is_control))
        {
            return Err(format!(
                "Racket executable must be a nonempty path of at most {MAX_RACKET_PATH_BYTES} bytes without control characters."
            ));
        }
        Ok(())
    }
}

/// Missing files use defaults. Other errors are returned so the UI can show a warning
/// and use defaults without changing a corrupt or unreadable file.
pub fn load() -> Result<Preferences, String> {
    load_from(config_path_with(|key| env::var_os(key))?)
}

/// Call only after an explicit setting change, never simply because the app started.
pub fn save(preferences: &Preferences) -> Result<(), String> {
    save_to(config_path_with(|key| env::var_os(key))?, preferences)
}

/// Explicit paths keep tests independent of the user's real configuration directory.
pub fn load_from(path: impl AsRef<Path>) -> Result<Preferences, String> {
    let path = path.as_ref();
    let file = match File::open(path) {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(Preferences::default());
        }
        Err(error) => {
            return Err(format!(
                "Could not read preferences at {}: {error}",
                path.display()
            ));
        }
    };
    // Bound the read itself, rather than relying on metadata which can change.
    let mut bytes = Vec::new();
    file.take(MAX_CONFIG_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|error| format!("Could not read preferences at {}: {error}", path.display()))?;
    if bytes.len() as u64 > MAX_CONFIG_BYTES {
        return Err(format!(
            "Preferences at {} exceed the 64 KiB size limit.",
            path.display()
        ));
    }
    // Serde's derived struct visitor also accepts positional arrays. Preferences
    // are an object-only format so an empty array must not silently become defaults.
    if bytes.iter().find(|byte| !byte.is_ascii_whitespace()) != Some(&b'{') {
        return Err(format!(
            "Invalid preferences at {}: expected a JSON object.",
            path.display()
        ));
    }
    let preferences: Preferences = serde_json::from_slice(&bytes)
        .map_err(|error| format!("Invalid preferences at {}: {error}", path.display()))?;
    preferences
        .validate()
        .map_err(|error| format!("Invalid preferences at {}: {error}", path.display()))?;
    Ok(preferences)
}

/// Writes a synced temporary file in the same directory, then atomically replaces
/// the destination. A failure before replacement leaves the existing file intact.
pub fn save_to(path: impl AsRef<Path>, preferences: &Preferences) -> Result<(), String> {
    let path = path.as_ref();
    preferences.validate()?;
    let mut bytes = serde_json::to_vec_pretty(preferences)
        .map_err(|error| format!("Could not encode preferences: {error}"))?;
    bytes.push(b'\n');
    let parent = path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    fs::create_dir_all(parent).map_err(|error| {
        format!(
            "Could not create preferences directory {}: {error}",
            parent.display()
        )
    })?;
    let mut temporary = tempfile::NamedTempFile::new_in(parent)
        .map_err(|error| format!("Could not create temporary preferences file: {error}"))?;
    temporary
        .write_all(&bytes)
        .and_then(|()| temporary.as_file().sync_all())
        .map_err(|error| format!("Could not write preferences at {}: {error}", path.display()))?;
    temporary.persist(path).map_err(|error| {
        format!(
            "Could not replace preferences at {}: {}",
            path.display(),
            error.error
        )
    })?;
    Ok(())
}

// Pure environment lookup permits testing location rules without mutating the
// process environment (which other tests or the running app may be using).
fn config_path_with(get: impl Fn(&str) -> Option<OsString>) -> Result<PathBuf, String> {
    let absolute = |key| {
        get(key)
            .map(PathBuf::from)
            .filter(|path| path.is_absolute())
    };
    #[cfg(target_os = "windows")]
    let directory = absolute("APPDATA").map(|path| path.join("OpenRacket"));
    #[cfg(target_os = "macos")]
    let directory =
        absolute("HOME").map(|path| path.join("Library/Application Support/OpenRacket"));
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    let directory = absolute("XDG_CONFIG_HOME")
        .or_else(|| absolute("HOME").map(|path| path.join(".config")))
        .map(|path| path.join("openracket"));

    directory
        .map(|path| path.join("preferences.json"))
        .ok_or_else(|| "Could not locate the user preferences directory.".into())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_file_returns_defaults_without_creating_anything() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("absent/preferences.json");
        assert_eq!(load_from(&path).unwrap(), Preferences::default());
        assert!(!path.parent().unwrap().exists());
    }

    #[test]
    fn settings_round_trip_and_replace_atomically_without_extra_files() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("nested/preferences.json");
        save_to(&path, &Preferences::default()).unwrap();
        let changed = Preferences {
            dark: false,
            font_size: 24.0,
            racket_path: Some("/Applications/Racket λ/bin/racket".into()),
            wrap: true,
            sidebar: false,
        };
        save_to(&path, &changed).unwrap();
        assert_eq!(load_from(&path).unwrap(), changed);
        assert_eq!(fs::read_dir(path.parent().unwrap()).unwrap().count(), 1);
        let object: serde_json::Value = serde_json::from_slice(&fs::read(path).unwrap()).unwrap();
        let mut keys = object
            .as_object()
            .unwrap()
            .keys()
            .map(String::as_str)
            .collect::<Vec<_>>();
        keys.sort_unstable();
        assert_eq!(
            keys,
            ["dark", "font_size", "racket_path", "sidebar", "wrap"]
        );
    }

    #[test]
    fn partial_config_uses_defaults_and_unknown_fields_are_ignored() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("preferences.json");
        fs::write(&path, r#"{"dark":false,"future_option":true}"#).unwrap();
        assert_eq!(
            load_from(path).unwrap(),
            Preferences {
                dark: false,
                ..Preferences::default()
            }
        );
    }

    #[test]
    fn corrupt_and_invalid_configs_are_reported_without_modification() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("preferences.json");
        for json in [
            "",
            "{",
            "null",
            "[]",
            r#"{"font_size":10}"#,
            r#"{"font_size":25}"#,
            r#"{"font_size":1e100}"#,
            r#"{"font_size":"large"}"#,
            r#"{"dark":null}"#,
            r#"{"racket_path":""}"#,
            r#"{"racket_path":"   "}"#,
            r#"{"racket_path":"racket\u0000"}"#,
            r#"{"racket_path":"racket\n"}"#,
        ] {
            fs::write(&path, json).unwrap();
            assert!(load_from(&path).is_err(), "accepted {json}");
            assert_eq!(fs::read_to_string(&path).unwrap(), json);
        }
        fs::write(&path, [0xff, 0xfe]).unwrap();
        assert!(load_from(&path).is_err());
    }

    #[test]
    fn oversized_file_and_executable_path_are_rejected() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("preferences.json");
        fs::write(&path, vec![b' '; MAX_CONFIG_BYTES as usize + 1]).unwrap();
        assert!(load_from(&path).unwrap_err().contains("size limit"));
        let json = serde_json::json!({"racket_path": "a".repeat(MAX_RACKET_PATH_BYTES + 1)});
        fs::write(&path, json.to_string()).unwrap();
        assert!(load_from(&path).is_err());
    }

    #[test]
    fn invalid_save_preserves_old_config_and_does_not_create_directories() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("preferences.json");
        save_to(&path, &Preferences::default()).unwrap();
        let before = fs::read(&path).unwrap();
        for font_size in [f32::NAN, f32::INFINITY, f32::NEG_INFINITY, 10.0, 25.0] {
            let invalid = Preferences {
                font_size,
                ..Preferences::default()
            };
            assert!(save_to(&path, &invalid).is_err());
            assert!(save_to(directory.path().join("new/config.json"), &invalid).is_err());
            assert_eq!(fs::read(&path).unwrap(), before);
        }
        assert!(!directory.path().join("new").exists());
    }

    #[test]
    fn unavailable_destination_and_failed_replacement_are_graceful() {
        let directory = tempfile::tempdir().unwrap();
        let occupied = directory.path().join("occupied");
        fs::write(&occupied, "keep me").unwrap();
        assert!(save_to(occupied.join("preferences.json"), &Preferences::default()).is_err());
        assert_eq!(fs::read_to_string(&occupied).unwrap(), "keep me");

        let target_directory = directory.path().join("preferences.json");
        fs::create_dir(&target_directory).unwrap();
        fs::write(target_directory.join("sentinel"), "unchanged").unwrap();
        assert!(load_from(&target_directory).is_err());
        assert!(save_to(&target_directory, &Preferences::default()).is_err());
        assert_eq!(
            fs::read_to_string(target_directory.join("sentinel")).unwrap(),
            "unchanged"
        );
        assert_eq!(fs::read_dir(directory.path()).unwrap().count(), 2);
    }

    #[test]
    fn font_range_boundaries_are_valid() {
        for font_size in [11.0, 15.5, 24.0] {
            assert!(
                Preferences {
                    font_size,
                    ..Preferences::default()
                }
                .validate()
                .is_ok()
            );
        }
    }

    #[test]
    fn missing_environment_returns_error_without_current_directory_fallback() {
        assert!(config_path_with(|_| None).is_err());
        assert!(config_path_with(|_| Some(OsString::from("relative"))).is_err());
        assert!(config_path_with(|_| Some(OsString::new())).is_err());
    }

    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    #[test]
    fn xdg_location_takes_precedence_and_relative_xdg_falls_back_to_home() {
        let path = config_path_with(|key| match key {
            "XDG_CONFIG_HOME" => Some(OsString::from("/test/config")),
            "HOME" => Some(OsString::from("/test/home")),
            _ => None,
        })
        .unwrap();
        assert_eq!(path, Path::new("/test/config/openracket/preferences.json"));
        for xdg in [
            None,
            Some(OsString::new()),
            Some(OsString::from("relative")),
        ] {
            let path = config_path_with(|key| match key {
                "XDG_CONFIG_HOME" => xdg.clone(),
                "HOME" => Some(OsString::from("/test/home")),
                _ => None,
            })
            .unwrap();
            assert_eq!(
                path,
                Path::new("/test/home/.config/openracket/preferences.json")
            );
        }
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn macos_uses_application_support() {
        let path =
            config_path_with(|key| (key == "HOME").then(|| OsString::from("/test/home"))).unwrap();
        assert_eq!(
            path,
            Path::new("/test/home/Library/Application Support/OpenRacket/preferences.json")
        );
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn windows_uses_roaming_appdata() {
        let path = config_path_with(|key| {
            (key == "APPDATA").then(|| OsString::from(r"C:\Users\test\AppData\Roaming"))
        })
        .unwrap();
        assert_eq!(
            path,
            Path::new(r"C:\Users\test\AppData\Roaming\OpenRacket\preferences.json")
        );
    }
}
