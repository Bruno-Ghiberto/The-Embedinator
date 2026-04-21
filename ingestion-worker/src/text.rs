use crate::types::{Chunk, DocType};

/// Maximum characters per chunk before attempting to split further.
const MAX_CHUNK_CHARS: usize = 4000;

/// Parse plain text content into chunks split at paragraph boundaries.
///
/// Splits on double newlines (paragraph boundaries). If a paragraph exceeds
/// MAX_CHUNK_CHARS, falls back to sentence boundary splitting.
pub fn parse_text(content: &str) -> Vec<Chunk> {
    let mut chunks = Vec::new();
    let mut chunk_index: usize = 0;
    let mut section_index: usize = 1;

    // Split on double newlines (paragraph boundaries)
    let paragraphs: Vec<&str> = content.split("\n\n").collect();

    let mut current_text = String::new();

    for para in &paragraphs {
        let trimmed = para.trim();
        if trimmed.is_empty() {
            continue;
        }

        // If adding this paragraph would exceed limit, flush current buffer
        if !current_text.is_empty() && current_text.len() + trimmed.len() + 2 > MAX_CHUNK_CHARS {
            chunks.push(Chunk::new(
                current_text.trim().to_string(),
                section_index,
                String::new(),
                vec![],
                DocType::Prose,
                chunk_index,
            ));
            chunk_index += 1;
            section_index += 1;
            current_text.clear();
        }

        // If a single paragraph exceeds limit, split by sentences
        if trimmed.len() > MAX_CHUNK_CHARS {
            // Flush any buffered text first
            if !current_text.is_empty() {
                chunks.push(Chunk::new(
                    current_text.trim().to_string(),
                    section_index,
                    String::new(),
                    vec![],
                    DocType::Prose,
                    chunk_index,
                ));
                chunk_index += 1;
                section_index += 1;
                current_text.clear();
            }

            // Split oversized paragraph by sentences
            let sentence_chunks = split_by_sentences(trimmed);
            for sent_chunk in sentence_chunks {
                chunks.push(Chunk::new(
                    sent_chunk,
                    section_index,
                    String::new(),
                    vec![],
                    DocType::Prose,
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

    // Flush remaining text
    if !current_text.trim().is_empty() {
        chunks.push(Chunk::new(
            current_text.trim().to_string(),
            section_index,
            String::new(),
            vec![],
            DocType::Prose,
            chunk_index,
        ));
    }

    chunks
}

/// Split text by sentence boundaries ('. ', '? ', '! '), grouping sentences
/// to stay under MAX_CHUNK_CHARS.
fn split_by_sentences(text: &str) -> Vec<String> {
    let mut results = Vec::new();
    let mut current = String::new();

    // Simple sentence splitting: look for '. ', '? ', '! ' followed by uppercase or end
    let mut chars = text.char_indices().peekable();
    let mut last_split = 0;

    while let Some((i, ch)) = chars.next() {
        if ch == '.' || ch == '?' || ch == '!' {
            // Check if next char is a space (sentence boundary)
            if let Some(&(_, next_ch)) = chars.peek() {
                if next_ch == ' ' || next_ch == '\n' {
                    let sentence = &text[last_split..=i];

                    if current.len() + sentence.len() > MAX_CHUNK_CHARS && !current.is_empty() {
                        results.push(current.trim().to_string());
                        current = String::new();
                    }
                    current.push_str(sentence);
                    // Skip the space
                    chars.next();
                    last_split = i + ch.len_utf8() + 1;
                }
            }
        }
    }

    // Remainder
    if last_split < text.len() {
        let remainder = &text[last_split..];
        if current.len() + remainder.len() > MAX_CHUNK_CHARS && !current.is_empty() {
            results.push(current.trim().to_string());
            current = String::new();
        }
        current.push_str(remainder);
    }

    if !current.trim().is_empty() {
        results.push(current.trim().to_string());
    }

    results
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_paragraphs() {
        let input = "Hello world.\n\nThis is paragraph two.\n\nAnd paragraph three.";
        let chunks = parse_text(input);
        // All fit under MAX_CHUNK_CHARS, so they're merged into one chunk
        assert!(!chunks.is_empty());
        assert!(chunks[0].text.contains("Hello world."));
        assert_eq!(chunks[0].doc_type, DocType::Prose);
        assert_eq!(chunks[0].chunk_index, 0);
        assert_eq!(chunks[0].chunk_profile, "default");
    }

    #[test]
    fn test_empty_input() {
        let chunks = parse_text("");
        assert!(chunks.is_empty());
    }

    #[test]
    fn test_whitespace_only() {
        let chunks = parse_text("   \n\n   \n\n   ");
        assert!(chunks.is_empty());
    }

    #[test]
    fn test_chunk_index_monotonic() {
        // Create enough paragraphs to force multiple chunks
        let para = "A".repeat(3000);
        let input = format!("{}\n\n{}\n\n{}", para, para, para);
        let chunks = parse_text(&input);
        for (i, chunk) in chunks.iter().enumerate() {
            assert_eq!(
                chunk.chunk_index, i,
                "chunk_index must be monotonically increasing"
            );
        }
    }

    #[test]
    fn test_doc_type_is_prose() {
        let chunks = parse_text("Some text content.");
        assert_eq!(chunks[0].doc_type, DocType::Prose);
    }

    #[test]
    fn test_heading_path_empty_for_text() {
        let chunks = parse_text("No headings here.");
        assert!(chunks[0].heading_path.is_empty());
    }

    #[test]
    fn test_no_empty_chunks_emitted() {
        let input = "text\n\n\n\n\n\nmore text";
        let chunks = parse_text(input);
        for chunk in &chunks {
            assert!(
                !chunk.text.trim().is_empty(),
                "Empty chunks must not be emitted"
            );
        }
    }
}
