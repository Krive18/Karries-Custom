import { SmartCreatePage } from "./SmartCreatePage";
import { VideoEditPage } from "./VideoEditPage";
import type {
  AgentVideoCreationHandoff,
  CreateMode,
  TaskCreateRequest,
  XHSAccountView
} from "../types";


type ContentWorkspacePageProps = {
  accounts: XHSAccountView[];
  mode: CreateMode;
  initialVideoHandoff?: AgentVideoCreationHandoff | null;
  onInitialVideoHandoffConsumed?: (key: string) => void;
  onCreateTask: (payload: TaskCreateRequest) => Promise<void>;
};


export function ContentWorkspacePage({
  accounts,
  mode,
  initialVideoHandoff = null,
  onInitialVideoHandoffConsumed,
  onCreateTask
}: ContentWorkspacePageProps) {
  return (
    <section className="content-workspace">
      {mode === "video"
        ? (
          <VideoEditPage
            initialHandoff={initialVideoHandoff}
            onInitialHandoffConsumed={onInitialVideoHandoffConsumed}
          />
        )
        : (
          <SmartCreatePage
            accounts={accounts}
            onCreateTask={onCreateTask}
          />
        )}
    </section>
  );
}
