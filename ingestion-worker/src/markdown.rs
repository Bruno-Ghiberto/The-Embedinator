use pulldown_cmark::{Event, HeadingLevel, Options, Parser, Tag, TagEnd};

use crate::heading_tracker::HeadingTracker;
use crate::types::{Chunk, DocType};

/// Parse Markdown content using pulldown-cmark, splitting at heading boundaries.
///
/// Splits at H1/H2/H3 headings. Uses HeadingTracker to maintain heading hierarchy.
/// Each section between headings becomes one chunk.
pub fn parse_markdown(content: &str) -> Vec<Chunk> {
    let options = Options::ENABLE_TABLES | Options::ENABLE_HEADING_ATTRIBUTES;
    let parser = Parser::new_ext(content, options);

    let mut chunks = Vec::new();
    let mut tracker = HeadingTracker::new();
    let mut chunk_index: usize = 0;
    let mut section_index: usize = 1;

    let mut current_text = String::new();
    let mut in_heading = false;
    let mut heading_level: usize = 0;
    let mut heading_text = String::new();

    for event in parser {
        match event {
            Event::Start(Tag::Heading { level, .. }) => {
                let lvl = heading_level_to_usize(level);

                // Only split on H1, H2, H3
                if lvl <= 3 {
                    // Flush accumulated text as a chunk
                    let trimmed = current_text.trim().to_string();
                    if !trimmed.is_empty() {
                        chunks.push(Chunk::new(
                            trimmed,
                            section_index,
                            tracker.current_section(),
                            tracker.path(),
                            DocType::Prose,
                            chunk_index,
                        ));
                        chunk_index += 1;
                        section_index += 1;
                    }
                    current_text.clear();
                    in_heading = true;
                    heading_level = lvl;
                    heading_text.clear();
                } else {
                    // H4+ headings are included in the text content
                    in_heading = false;
                }
            }
            Event::End(TagEnd::Heading(_)) => {
                if in_heading {
                    tracker.push(heading_level, heading_text.trim().to_string());
                    in_heading = false;
                }
            }
            Event::Text(text) => {
                if in_heading {
                    heading_text.push_str(&text);
                } else {
                    current_text.push_str(&text);
                }
            }
            Event::Code(code) => {
                if in_heading {
                    heading_text.push_str(&code);
                } else {
                    current_text.push('`');
                    current_text.push_str(&code);
                    current_text.push('`');
                }
            }
            Event::SoftBreak | Event::HardBreak => {
                if in_heading {
                    heading_text.push(' ');
                } else {
                    current_text.push('\n');
                }
            }
            Event::Start(Tag::Paragraph) => {}
            Event::End(TagEnd::Paragraph) => {
                current_text.push_str("\n\n");
            }
            Event::Start(Tag::CodeBlock(_)) => {
                current_text.push_str("\n```\n");
            }
            Event::End(TagEnd::CodeBlock) => {
                current_text.push_str("```\n\n");
            }
            Event::Start(Tag::List(_)) => {}
            Event::End(TagEnd::List(_)) => {
                current_text.push('\n');
            }
            Event::Start(Tag::Item) => {
                current_text.push_str("- ");
            }
            Event::End(TagEnd::Item) => {
                current_text.push('\n');
            }
            _ => {}
        }
    }

    // Flush final chunk
    let trimmed = current_text.trim().to_string();
    if !trimmed.is_empty() {
        chunks.push(Chunk::new(
            trimmed,
            section_index,
            tracker.current_section(),
            tracker.path(),
            DocType::Prose,
            chunk_index,
        ));
    }

    chunks
}

fn heading_level_to_usize(level: HeadingLevel) -> usize {
    match level {
        HeadingLevel::H1 => 1,
        HeadingLevel::H2 => 2,
        HeadingLevel::H3 => 3,
        HeadingLevel::H4 => 4,
        HeadingLevel::H5 => 5,
        HeadingLevel::H6 => 6,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_markdown() {
        let input = "# Hello\n\nSome content here.\n\n## Section 2\n\nMore content.";
        let chunks = parse_markdown(input);
        assert!(chunks.len() >= 2);
        assert_eq!(chunks[0].doc_type, DocType::Prose);
    }

    #[test]
    fn test_heading_hierarchy() {
        let input = "# Chapter 1\n\nIntro\n\n## Section 1.1\n\nDetails\n\n## Section 1.2\n\nMore";
        let chunks = parse_markdown(input);

        // First chunk: intro under "Chapter 1"
        assert_eq!(chunks[0].heading_path, vec!["Chapter 1"]);
        assert_eq!(chunks[0].section, "Chapter 1");

        // Second chunk: under "Chapter 1" > "Section 1.1"
        assert_eq!(chunks[1].heading_path, vec!["Chapter 1", "Section 1.1"]);

        // Third chunk: under "Chapter 1" > "Section 1.2"
        assert_eq!(chunks[2].heading_path, vec!["Chapter 1", "Section 1.2"]);
    }

    #[test]
    fn test_no_headings() {
        let input = "Just plain text with no headings.";
        let chunks = parse_markdown(input);
        assert_eq!(chunks.len(), 1);
        assert!(chunks[0].heading_path.is_empty());
        assert_eq!(chunks[0].section, "");
    }

    #[test]
    fn test_chunk_index_monotonic() {
        let input = "# A\n\nText\n\n# B\n\nText\n\n# C\n\nText";
        let chunks = parse_markdown(input);
        for (i, chunk) in chunks.iter().enumerate() {
            assert_eq!(chunk.chunk_index, i);
        }
    }

    #[test]
    fn test_h4_not_split() {
        let input = "# Main\n\nPre\n\n#### Detail\n\nPost";
        let chunks = parse_markdown(input);
        // H4 should not cause a split — all text under "Main" in one chunk
        assert_eq!(chunks.len(), 1);
    }

    #[test]
    fn test_empty_markdown() {
        let chunks = parse_markdown("");
        assert!(chunks.is_empty());
    }

    #[test]
    fn test_heading_path_consistency() {
        let input = "# A\n\n## B\n\nChunk text";
        let chunks = parse_markdown(input);
        let last = chunks.last().unwrap();
        assert_eq!(last.heading_path, vec!["A", "B"]);
    }

    #[test]
    fn test_no_empty_chunks() {
        let input = "# A\n\n\n\n# B\n\nContent";
        let chunks = parse_markdown(input);
        for chunk in &chunks {
            assert!(!chunk.text.trim().is_empty());
        }
    }
}
