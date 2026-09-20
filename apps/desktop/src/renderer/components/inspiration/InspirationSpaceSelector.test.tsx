import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { InspirationSpaceSelector } from "./InspirationSpaceSelector";


describe("InspirationSpaceSelector", () => {
  it("opens a spacious custom menu and switches conversation spaces", () => {
    const onChange = vi.fn();
    const onManage = vi.fn();
    render(
      <InspirationSpaceSelector
        space={{ interaction_mode: "normal", personalization_template_id: 0 }}
        templates={[{
          id: 7,
          tenant_id: 1,
          user_id: 2,
          template_name: "品牌主理人",
          assistant_name: "Karries AI",
          assistant_traits: "保持品牌语气",
          preferred_address: "主理人",
          occupation: "品牌运营",
          user_details: "",
          response_preferences: "简洁",
          status: "active",
          create_time: 1,
          update_time: 1
        }]}
        onChange={onChange}
        onManage={onManage}
      />
    );

    const trigger = screen.getByRole("button", { name: "对话模式：普通对话" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("listbox", { name: "选择对话模式" })).not.toBeInTheDocument();

    fireEvent.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("listbox", { name: "选择对话模式" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: /品牌主理人/ }));
    expect(onChange).toHaveBeenCalledWith({
      interaction_mode: "personalized",
      personalization_template_id: 7
    });

    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole("button", { name: "管理个性化模板" }));
    expect(onManage).toHaveBeenCalledTimes(1);
  });
});
