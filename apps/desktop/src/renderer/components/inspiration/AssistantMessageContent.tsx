import { memo } from "react";

import { RichContentMarkdown } from "../content/RichContentReader";

type AssistantMessageContentProps = {
  content: string;
};

export const AssistantMessageContent = memo(function AssistantMessageContent({
  content
}: AssistantMessageContentProps) {
  return <RichContentMarkdown content={content} className="assistant-markdown" />;
});
