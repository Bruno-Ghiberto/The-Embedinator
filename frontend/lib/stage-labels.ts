export const stageLabels: Record<string, string> = {
  intent_analysis: "Understanding your question...",
  research: "Searching documents...",
  tools_node: "Retrieving sources...",
  compress_check: "Analyzing relevance...",
  generate_response: "Writing response...",
  verify_groundedness: "Verifying accuracy...",
  evaluate_confidence: "Assessing confidence...",
}

export function getStageLabel(node: string): string {
  return stageLabels[node] ?? node
}
