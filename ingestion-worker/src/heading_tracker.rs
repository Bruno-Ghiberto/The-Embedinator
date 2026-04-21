/// Tracks the current heading hierarchy in a document.
///
/// Maintains a stack of (level, text) pairs. When a new heading is pushed,
/// all headings at the same or deeper level are removed first.
#[derive(Debug, Default)]
pub struct HeadingTracker {
    stack: Vec<(usize, String)>,
}

impl HeadingTracker {
    pub fn new() -> Self {
        Self { stack: Vec::new() }
    }

    /// Push a heading at the given level. Removes all entries at the same
    /// or deeper level before inserting.
    pub fn push(&mut self, level: usize, text: String) {
        self.stack.retain(|&(l, _)| l < level);
        self.stack.push((level, text));
    }

    /// Returns the current heading hierarchy as a list of heading texts.
    pub fn path(&self) -> Vec<String> {
        self.stack.iter().map(|(_, t)| t.clone()).collect()
    }

    /// Returns the deepest (most specific) heading text, or empty string.
    pub fn current_section(&self) -> String {
        self.stack
            .last()
            .map(|(_, t)| t.clone())
            .unwrap_or_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_tracker() {
        let tracker = HeadingTracker::new();
        assert!(tracker.path().is_empty());
        assert_eq!(tracker.current_section(), "");
    }

    #[test]
    fn test_single_heading() {
        let mut tracker = HeadingTracker::new();
        tracker.push(1, "Chapter 1".to_string());
        assert_eq!(tracker.path(), vec!["Chapter 1"]);
        assert_eq!(tracker.current_section(), "Chapter 1");
    }

    #[test]
    fn test_nested_headings() {
        let mut tracker = HeadingTracker::new();
        tracker.push(1, "Chapter 1".to_string());
        tracker.push(2, "Section 1.1".to_string());
        tracker.push(3, "Subsection 1.1.1".to_string());
        assert_eq!(
            tracker.path(),
            vec!["Chapter 1", "Section 1.1", "Subsection 1.1.1"]
        );
    }

    #[test]
    fn test_same_level_replaces() {
        let mut tracker = HeadingTracker::new();
        tracker.push(1, "Chapter 1".to_string());
        tracker.push(2, "Section 1.1".to_string());
        tracker.push(2, "Section 1.2".to_string());
        assert_eq!(tracker.path(), vec!["Chapter 1", "Section 1.2"]);
    }

    #[test]
    fn test_higher_level_clears_deeper() {
        let mut tracker = HeadingTracker::new();
        tracker.push(1, "Chapter 1".to_string());
        tracker.push(2, "Section 1.1".to_string());
        tracker.push(3, "Sub 1.1.1".to_string());
        tracker.push(1, "Chapter 2".to_string());
        assert_eq!(tracker.path(), vec!["Chapter 2"]);
    }

    #[test]
    fn test_heading_path_consistency() {
        // Invariant 4: heading_path must be consistent within a section
        let mut tracker = HeadingTracker::new();
        tracker.push(1, "A".to_string());
        tracker.push(2, "B".to_string());

        let path1 = tracker.path();
        let path2 = tracker.path();
        assert_eq!(path1, path2, "Multiple calls to path() must be consistent");
        assert_eq!(path1, vec!["A", "B"]);
    }
}
