import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Settings2, UserRoundCog } from "lucide-react";

import type { InspirationPersonalizationTemplate } from "../../types";


export type InspirationConversationSpace = {
  interaction_mode: "normal" | "personalized";
  personalization_template_id: number;
};

export function conversationSpaceValue(space: InspirationConversationSpace) {
  return space.interaction_mode === "normal"
    ? "normal"
    : `template:${space.personalization_template_id}`;
}

export function InspirationSpaceSelector({
  space,
  templates,
  onChange,
  onManage
}: {
  space: InspirationConversationSpace;
  templates: InspirationPersonalizationTemplate[];
  onChange: (space: InspirationConversationSpace) => void;
  onManage: () => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const selectorRef = useRef<HTMLDivElement>(null);
  const activeTemplates = templates.filter((template) => template.status === "active");
  const currentLabel = space.interaction_mode === "normal"
    ? "普通对话"
    : templates.find(
      (template) => template.id === space.personalization_template_id
    )?.template_name ?? "个性化模板";

  useEffect(() => {
    if (!isOpen) return undefined;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!selectorRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isOpen]);

  return (
    <div
      className={isOpen ? "inspiration-space-selector is-open" : "inspiration-space-selector"}
      ref={selectorRef}
    >
      <button
        className="inspiration-space-trigger"
        type="button"
        aria-label={`对话模式：${currentLabel}`}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
      >
        <UserRoundCog size={16} aria-hidden="true" />
        <span className="inspiration-space-selector-current">{currentLabel}</span>
        <ChevronDown className="inspiration-space-chevron" size={15} aria-hidden="true" />
      </button>
      {isOpen ? (
        <div className="inspiration-space-menu" role="listbox" aria-label="选择对话模式">
          <button
            className={space.interaction_mode === "normal" ? "selected" : ""}
            type="button"
            role="option"
            aria-selected={space.interaction_mode === "normal"}
            onClick={() => {
              onChange({ interaction_mode: "normal", personalization_template_id: 0 });
              setIsOpen(false);
            }}
          >
            <span><strong>普通对话</strong><small>不自动加入创作上下文</small></span>
            {space.interaction_mode === "normal" ? <Check size={15} aria-hidden="true" /> : null}
          </button>
          {activeTemplates.map((template) => {
            const isSelected = conversationSpaceValue(space) === `template:${template.id}`;
            return (
              <button
                className={isSelected ? "selected" : ""}
                key={template.id}
                type="button"
                role="option"
                aria-selected={isSelected}
                onClick={() => {
                  onChange({
                    interaction_mode: "personalized",
                    personalization_template_id: template.id
                  });
                  setIsOpen(false);
                }}
              >
                <span><strong>{template.template_name}</strong><small>个性化模板</small></span>
                {isSelected ? <Check size={15} aria-hidden="true" /> : null}
              </button>
            );
          })}
          <button
            className="inspiration-space-manage"
            type="button"
            onClick={() => {
              setIsOpen(false);
              onManage();
            }}
          >
            <Settings2 size={15} aria-hidden="true" />
            管理个性化模板
          </button>
        </div>
      ) : null}
    </div>
  );
}
