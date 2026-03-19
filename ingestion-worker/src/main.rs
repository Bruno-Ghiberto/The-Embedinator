mod code;
mod heading_tracker;
mod markdown;
mod pdf;
mod text;
mod types;

use std::path::Path;

use clap::Parser;

use crate::code::is_code_extension;
use crate::types::Chunk;

#[derive(Parser)]
#[command(name = "embedinator-worker", about = "Document parsing worker")]
struct Cli {
    /// Path to the input file
    #[arg(long)]
    file: String,

    /// Document type hint (pdf, markdown, text, code). Auto-detected from extension if omitted.
    #[arg(long = "type")]
    doc_type: Option<String>,
}

/// Detect document type from file extension.
fn detect_type(path: &Path) -> Option<&'static str> {
    let ext = path.extension()?.to_str()?;
    match ext {
        "pdf" => Some("pdf"),
        "md" => Some("markdown"),
        "txt" => Some("text"),
        _ if is_code_extension(ext) => Some("code"),
        _ => None,
    }
}

fn main() {
    let cli = Cli::parse();
    let path = Path::new(&cli.file);

    // Validate file exists
    if !path.exists() {
        eprintln!("[ERROR] File not found: {}", cli.file);
        std::process::exit(1);
    }

    // Determine document type
    let doc_type = match &cli.doc_type {
        Some(t) => t.as_str(),
        None => match detect_type(path) {
            Some(t) => t,
            None => {
                eprintln!(
                    "[ERROR] Cannot detect file type for '{}'. Use --type to specify.",
                    cli.file
                );
                std::process::exit(1);
            }
        },
    };

    // Dispatch to parser and collect chunks
    let result: Result<Vec<Chunk>, (Vec<Chunk>, String)> = match doc_type {
        "pdf" => pdf::parse_pdf(path),
        "markdown" => {
            match std::fs::read_to_string(path) {
                Ok(content) => Ok(markdown::parse_markdown(&content)),
                Err(e) => Err((Vec::new(), format!("Failed to read file: {}", e))),
            }
        }
        "text" => {
            match std::fs::read_to_string(path) {
                Ok(content) => Ok(text::parse_text(&content)),
                Err(e) => Err((Vec::new(), format!("Failed to read file: {}", e))),
            }
        }
        "code" => {
            match std::fs::read_to_string(path) {
                Ok(content) => Ok(code::parse_code(&content)),
                Err(e) => Err((Vec::new(), format!("Failed to read file: {}", e))),
            }
        }
        _ => {
            eprintln!("[ERROR] Unsupported document type: {}", doc_type);
            std::process::exit(1);
        }
    };

    match result {
        Ok(chunks) => {
            emit_chunks(&chunks);
            std::process::exit(0);
        }
        Err((partial_chunks, error_msg)) => {
            // Emit any partial output before reporting error (R4)
            emit_chunks(&partial_chunks);
            eprintln!("[ERROR] {}", error_msg);
            std::process::exit(2);
        }
    }
}

/// Write chunks as NDJSON lines to stdout.
fn emit_chunks(chunks: &[Chunk]) {
    for chunk in chunks {
        match serde_json::to_string(chunk) {
            Ok(json) => println!("{}", json),
            Err(e) => eprintln!("[ERROR] Failed to serialize chunk: {}", e),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    #[test]
    fn test_detect_type_pdf() {
        assert_eq!(detect_type(Path::new("doc.pdf")), Some("pdf"));
    }

    #[test]
    fn test_detect_type_markdown() {
        assert_eq!(detect_type(Path::new("readme.md")), Some("markdown"));
    }

    #[test]
    fn test_detect_type_text() {
        assert_eq!(detect_type(Path::new("notes.txt")), Some("text"));
    }

    #[test]
    fn test_detect_type_code_extensions() {
        assert_eq!(detect_type(Path::new("main.py")), Some("code"));
        assert_eq!(detect_type(Path::new("app.js")), Some("code"));
        assert_eq!(detect_type(Path::new("lib.ts")), Some("code"));
        assert_eq!(detect_type(Path::new("main.rs")), Some("code"));
        assert_eq!(detect_type(Path::new("main.go")), Some("code"));
        assert_eq!(detect_type(Path::new("App.java")), Some("code"));
        assert_eq!(detect_type(Path::new("main.c")), Some("code"));
        assert_eq!(detect_type(Path::new("main.cpp")), Some("code"));
        assert_eq!(detect_type(Path::new("header.h")), Some("code"));
    }

    #[test]
    fn test_detect_type_unknown() {
        assert_eq!(detect_type(Path::new("file.exe")), None);
        assert_eq!(detect_type(Path::new("file.zip")), None);
    }

    #[test]
    fn test_detect_type_no_extension() {
        assert_eq!(detect_type(Path::new("Makefile")), None);
    }

    #[test]
    fn test_ndjson_output_valid_json() {
        let chunk = types::Chunk::new(
            "test text".to_string(),
            1,
            "Section".to_string(),
            vec!["H1".to_string()],
            types::DocType::Prose,
            0,
        );
        let json = serde_json::to_string(&chunk).unwrap();
        // Must be parseable as JSON
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed["text"], "test text");
        assert_eq!(parsed["chunk_index"], 0);
    }
}
