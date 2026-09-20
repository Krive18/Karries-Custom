export function composeInspirationPrompt(currentPrompt: string, quotedPrompt?: string): string {
  const nextPrompt = currentPrompt.trim();
  const reference = quotedPrompt?.trim() ?? "";
  if (!reference) return nextPrompt;

  const quotedLines = reference.split(/\r?\n/).map((line) => `> ${line}`);
  return [
    "引用之前的提示词：",
    ...quotedLines,
    "",
    "当前请求：",
    nextPrompt
  ].join("\n");
}
