use std::path::Path;

use crate::types::{Chunk, DocType};

/// Parse a PDF file page-by-page, emitting chunks with page numbers.
///
/// Uses pdf-extract's `extract_text_by_pages` for page-by-page extraction.
/// Skips image-only pages (empty text) with a warning to stderr.
/// Returns Ok(chunks) on success, or Err with any chunks produced before failure.
pub fn parse_pdf(path: &Path) -> Result<Vec<Chunk>, (Vec<Chunk>, String)> {
    let pages = pdf_extract::extract_text_by_pages(path).map_err(|e| {
        (Vec::new(), format!("Failed to open PDF: {}", e))
    })?;

    let mut chunks = Vec::new();
    let mut chunk_index: usize = 0;

    for (page_num_0, page_text) in pages.iter().enumerate() {
        let page_num = page_num_0 + 1; // 1-indexed

        let trimmed = page_text.trim();
        if trimmed.is_empty() {
            eprintln!(
                "[WARN] Page {}: no extractable text (image-only page)",
                page_num
            );
            continue;
        }

        chunks.push(Chunk::new(
            trimmed.to_string(),
            page_num,
            String::new(),
            vec![],
            DocType::Prose,
            chunk_index,
        ));
        chunk_index += 1;
    }

    Ok(chunks)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_nonexistent_pdf_returns_error() {
        let result = parse_pdf(Path::new("/tmp/_nonexistent_test_file.pdf"));
        assert!(result.is_err());
    }

    #[test]
    fn test_invalid_pdf_returns_error() {
        // Create a temporary file with invalid PDF content
        let path = Path::new("/tmp/_embedinator_test_invalid.pdf");
        std::fs::write(path, b"not a pdf").unwrap();
        let result = parse_pdf(path);
        assert!(result.is_err());
        std::fs::remove_file(path).ok();
    }
}
