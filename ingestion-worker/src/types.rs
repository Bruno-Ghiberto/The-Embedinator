use serde::Serialize;

/// Document type classification for chunks.
#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum DocType {
    Prose,
    Code,
}

/// A single parsed text chunk emitted as one NDJSON line.
#[derive(Debug, Clone, Serialize)]
pub struct Chunk {
    pub text: String,
    pub page: usize,
    pub section: String,
    pub heading_path: Vec<String>,
    pub doc_type: DocType,
    pub chunk_profile: String,
    pub chunk_index: usize,
}

impl Chunk {
    pub fn new(
        text: String,
        page: usize,
        section: String,
        heading_path: Vec<String>,
        doc_type: DocType,
        chunk_index: usize,
    ) -> Self {
        Self {
            text,
            page,
            section,
            heading_path,
            doc_type,
            chunk_profile: "default".to_string(),
            chunk_index,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_doc_type_serializes_lowercase() {
        assert_eq!(serde_json::to_string(&DocType::Prose).unwrap(), "\"prose\"");
        assert_eq!(serde_json::to_string(&DocType::Code).unwrap(), "\"code\"");
    }

    #[test]
    fn test_chunk_serializes_to_valid_json() {
        let chunk = Chunk::new(
            "Hello world".to_string(),
            1,
            "Introduction".to_string(),
            vec!["Chapter 1".to_string(), "Introduction".to_string()],
            DocType::Prose,
            0,
        );
        let json = serde_json::to_string(&chunk).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();

        assert_eq!(parsed["text"], "Hello world");
        assert_eq!(parsed["page"], 1);
        assert_eq!(parsed["section"], "Introduction");
        assert_eq!(parsed["heading_path"][0], "Chapter 1");
        assert_eq!(parsed["heading_path"][1], "Introduction");
        assert_eq!(parsed["doc_type"], "prose");
        assert_eq!(parsed["chunk_profile"], "default");
        assert_eq!(parsed["chunk_index"], 0);
    }

    #[test]
    fn test_chunk_profile_always_default() {
        let chunk = Chunk::new("text".into(), 1, "".into(), vec![], DocType::Code, 5);
        assert_eq!(chunk.chunk_profile, "default");
    }

    #[test]
    fn test_chunk_has_all_required_fields() {
        let chunk = Chunk::new("t".into(), 0, "".into(), vec![], DocType::Prose, 0);
        let json = serde_json::to_string(&chunk).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();

        // All 7 fields must be present
        assert!(parsed.get("text").is_some());
        assert!(parsed.get("page").is_some());
        assert!(parsed.get("section").is_some());
        assert!(parsed.get("heading_path").is_some());
        assert!(parsed.get("doc_type").is_some());
        assert!(parsed.get("chunk_profile").is_some());
        assert!(parsed.get("chunk_index").is_some());
    }
}
