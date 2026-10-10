use crate::document::decode_file;
use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
    sync::Arc,
};

pub const MAX_FILE_BYTES: u64 = 16 * 1024 * 1024;
#[derive(Clone, Debug)]
pub struct LoadedFile {
    pub path: PathBuf,
    pub text: Arc<String>,
}
pub fn load(path: PathBuf) -> Result<LoadedFile, String> {
    let path =
        fs::canonicalize(&path).map_err(|e| format!("Could not open {}: {e}", path.display()))?;
    let size = fs::metadata(&path).map_err(|e| e.to_string())?.len();
    if size > MAX_FILE_BYTES {
        return Err("This prototype opens files up to 16 MiB. The file was left unchanged.".into());
    }
    let text = decode_file(fs::read(&path).map_err(|e| e.to_string())?)?;
    Ok(LoadedFile {
        path,
        text: Arc::new(text),
    })
}
/// Same-directory temporary file + fsync + atomic rename. A failed save preserves the original.
pub fn save(
    path: PathBuf,
    text: Arc<String>,
    expected: Option<Arc<String>>,
    force: bool,
) -> Result<PathBuf, String> {
    if path.exists()
        && !force
        && let Some(expected) = expected
    {
        let actual =
            fs::read_to_string(&path).map_err(|e| format!("Could not verify current file: {e}"))?;
        if actual.as_str() != expected.as_str() {
            return Err("This file changed on disk. Your edits are safe. Use Save As to save a separate copy, or reopen the file to compare.".into());
        }
    }
    let parent = path
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let mut temporary = tempfile::NamedTempFile::new_in(parent)
        .map_err(|e| format!("Could not create a safe save file: {e}"))?;
    if let Ok(meta) = fs::metadata(&path) {
        fs::set_permissions(temporary.path(), meta.permissions()).map_err(|e| e.to_string())?;
    }
    temporary
        .write_all(text.as_bytes())
        .map_err(|e| format!("Save failed: {e}"))?;
    temporary
        .as_file()
        .sync_all()
        .map_err(|e| format!("Save failed: {e}"))?;
    temporary
        .persist(&path)
        .map_err(|e| format!("Save failed; original file preserved: {}", e.error))?;
    Ok(path)
}
pub fn workspace_files(path: &Path) -> Vec<PathBuf> {
    let mut files = fs::read_dir(path)
        .ok()
        .into_iter()
        .flatten()
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| {
            p.is_file()
                && p.extension()
                    .is_some_and(|e| e == "rkt" || e == "rktd" || e == "scm" || e == "ss")
        })
        .take(200)
        .collect::<Vec<_>>();
    files.sort();
    files
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn atomic_save_and_external_change_detection() {
        let dir = tempfile::tempdir().unwrap();
        let p = dir.path().join("a.rkt");
        fs::write(&p, "original").unwrap();
        let before = Arc::new("original".to_string());
        save(p.clone(), Arc::new("new".into()), Some(before), false).unwrap();
        assert_eq!(fs::read_to_string(&p).unwrap(), "new");
        fs::write(&p, "external").unwrap();
        assert!(
            save(
                p.clone(),
                Arc::new("mine".into()),
                Some(Arc::new("new".into())),
                false
            )
            .is_err()
        );
        assert_eq!(fs::read_to_string(&p).unwrap(), "external");
    }
    #[test]
    fn save_failure_keeps_buffer_value() {
        let value: Arc<String> = Arc::new("λ and 你好".into());
        assert!(
            save(
                PathBuf::from("/not/a/real/directory/a.rkt"),
                value.clone(),
                None,
                false
            )
            .is_err()
        );
        assert_eq!(value.as_str(), "λ and 你好");
    }
    #[test]
    fn plain_utf8_load() {
        let dir = tempfile::tempdir().unwrap();
        let p = dir.path().join("λ.rkt");
        fs::write(&p, "#lang racket\n\"你好\"\n").unwrap();
        assert_eq!(load(p).unwrap().text.as_str(), "#lang racket\n\"你好\"\n");
    }
}
