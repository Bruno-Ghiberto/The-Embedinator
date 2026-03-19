use crate::types::{Chunk, DocType};

/// Maximum characters per code chunk.
const MAX_CHUNK_CHARS: usize = 4000;

/// Supported code file extensions.
pub const CODE_EXTENSIONS: &[&str] = &[
    "py", "js", "ts", "rs", "go", "java", "c", "cpp", "h",
];

/// Check if a file extension is a supported code type.
pub fn is_code_extension(ext: &str) -> bool {
    CODE_EXTENSIONS.contains(&ext)
}

/// Parse code file content into chunks at paragraph boundaries.
///
/// Splits on double newlines (blank lines between code blocks/functions).
/// Emits chunks with doc_type Code.
pub fn parse_code(content: &str) -> Vec<Chunk> {
    let mut chunks = Vec::new();
    let mut chunk_index: usize = 0;
    let mut section_index: usize = 1;

    let blocks: Vec<&str> = content.split("\n\n").collect();
    let mut current_text = String::new();

    for block in &blocks {
        let trimmed = block.trim();
        if trimmed.is_empty() {
            continue;
        }

        // If adding this block would exceed limit, flush
        if !current_text.is_empty()
            && current_text.len() + trimmed.len() + 2 > MAX_CHUNK_CHARS
        {
            chunks.push(Chunk::new(
                current_text.trim().to_string(),
                section_index,
                String::new(),
                vec![],
                DocType::Code,
                chunk_index,
            ));
            chunk_index += 1;
            section_index += 1;
            current_text.clear();
        }

        // Single block too large — split by lines
        if trimmed.len() > MAX_CHUNK_CHARS {
            if !current_text.is_empty() {
                chunks.push(Chunk::new(
                    current_text.trim().to_string(),
                    section_index,
                    String::new(),
                    vec![],
                    DocType::Code,
                    chunk_index,
                ));
                chunk_index += 1;
                section_index += 1;
                current_text.clear();
            }

            let line_chunks = split_by_lines(trimmed);
            for lc in line_chunks {
                chunks.push(Chunk::new(
                    lc,
                    section_index,
                    String::new(),
                    vec![],
                    DocType::Code,
                    chunk_index,
                ));
                chunk_index += 1;
            }
            section_index += 1;
        } else {
            if !current_text.is_empty() {
                current_text.push_str("\n\n");
            }
            current_text.push_str(trimmed);
        }
    }

    // Flush remaining
    if !current_text.trim().is_empty() {
        chunks.push(Chunk::new(
            current_text.trim().to_string(),
            section_index,
            String::new(),
            vec![],
            DocType::Code,
            chunk_index,
        ));
    }

    chunks
}

/// Split oversized text by lines, grouping to stay under MAX_CHUNK_CHARS.
fn split_by_lines(text: &str) -> Vec<String> {
    let mut results = Vec::new();
    let mut current = String::new();

    for line in text.lines() {
        if current.len() + line.len() + 1 > MAX_CHUNK_CHARS && !current.is_empty() {
            results.push(current.trim_end().to_string());
            current = String::new();
        }
        if !current.is_empty() {
            current.push('\n');
        }
        current.push_str(line);
    }

    if !current.trim().is_empty() {
        results.push(current.trim_end().to_string());
    }

    results
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_code() {
        let input = "def hello():\n    pass";
        let chunks = parse_code(input);
        assert_eq!(chunks.len(), 1);
        assert_eq!(chunks[0].doc_type, DocType::Code);
        assert_eq!(chunks[0].chunk_index, 0);
    }

    #[test]
    fn test_code_extensions() {
        assert!(is_code_extension("py"));
        assert!(is_code_extension("js"));
        assert!(is_code_extension("ts"));
        assert!(is_code_extension("rs"));
        assert!(is_code_extension("go"));
        assert!(is_code_extension("java"));
        assert!(is_code_extension("c"));
        assert!(is_code_extension("cpp"));
        assert!(is_code_extension("h"));
        assert!(!is_code_extension("txt"));
        assert!(!is_code_extension("pdf"));
        assert!(!is_code_extension("md"));
    }

    #[test]
    fn test_multiple_functions() {
        let input = "def foo():\n    pass\n\ndef bar():\n    pass\n\ndef baz():\n    pass";
        let chunks = parse_code(input);
        assert!(!chunks.is_empty());
        for chunk in &chunks {
            assert_eq!(chunk.doc_type, DocType::Code);
        }
    }

    #[test]
    fn test_empty_code() {
        let chunks = parse_code("");
        assert!(chunks.is_empty());
    }

    #[test]
    fn test_heading_path_empty_for_code() {
        let chunks = parse_code("int main() { return 0; }");
        assert!(chunks[0].heading_path.is_empty());
    }

    #[test]
    fn test_no_empty_chunks() {
        let input = "code\n\n\n\n\n\nmore code";
        let chunks = parse_code(input);
        for chunk in &chunks {
            assert!(!chunk.text.trim().is_empty());
        }
    }
}
