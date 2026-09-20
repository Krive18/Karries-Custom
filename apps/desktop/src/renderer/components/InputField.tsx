import type { ChangeEventHandler, HTMLInputTypeAttribute, ReactNode } from "react";

type InputFieldProps = {
  id: string;
  label: string;
  name: string;
  type?: HTMLInputTypeAttribute;
  value: string;
  placeholder: string;
  autoComplete: string;
  icon: ReactNode;
  endAction?: ReactNode;
  autoFocus?: boolean;
  onChange: ChangeEventHandler<HTMLInputElement>;
};

export function InputField({
  id,
  label,
  name,
  type = "text",
  value,
  placeholder,
  autoComplete,
  icon,
  endAction,
  autoFocus = false,
  onChange
}: InputFieldProps) {
  return (
    <div className="lux-login-field">
      <label htmlFor={id}>{label}</label>
      <div className="lux-login-input">
        <span className="lux-login-input__icon" aria-hidden="true">{icon}</span>
        <input
          id={id}
          name={name}
          type={type}
          value={value}
          placeholder={placeholder}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          onChange={onChange}
        />
        {endAction ? <span className="lux-login-input__action">{endAction}</span> : null}
      </div>
    </div>
  );
}
