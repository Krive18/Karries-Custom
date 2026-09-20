import { useState, type FormEvent } from "react";
import {
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
  UserRound
} from "lucide-react";

import { brandAssets } from "../assets";
import type { Portal } from "../auth/portalSession";
import type { LoginRequest } from "../types";
import { InputField } from "./InputField";
import { SecurityBadge } from "./SecurityBadge";

type LoginCardProps = {
  portal: Portal;
  eyebrow: string;
  title: string;
  description: string;
  accessLabel: string;
  error: string;
  isSubmitting: boolean;
  onSubmit: (credentials: LoginRequest) => Promise<void>;
};

export function LoginCard({
  portal,
  eyebrow,
  title,
  description,
  accessLabel,
  error,
  isSubmitting,
  onSubmit
}: LoginCardProps) {
  const [loginName, setLoginName] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting || !loginName.trim() || !password) return;
    void onSubmit({ login_name: loginName.trim(), password });
  };

  return (
    <form className={`lux-login-card lux-login-card--${portal}`} onSubmit={handleSubmit}>
      <header className="lux-login-card__header">
        {portal === "developer" ? (
          <span className="lux-login-card__secure-index">SECURE LOGIN / 01</span>
        ) : (
          <span className="lux-login-card__emblem">
            <img src={brandAssets.monogram} alt="" />
          </span>
        )}
        <span className="lux-login-card__eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
        <p>{description}</p>
        {portal === "developer" ? null : (
          <span className="lux-login-card__divider" aria-hidden="true">
            <i />
            <b>✦</b>
            <i />
          </span>
        )}
      </header>

      <div className="lux-login-card__fields">
        <InputField
          id={`${portal}-login-name`}
          label="登录账号"
          name="login_name"
          value={loginName}
          placeholder="请输入登录账号"
          autoComplete="username"
          icon={portal === "developer" ? <ShieldCheck size={20} /> : <UserRound size={20} />}
          autoFocus
          onChange={(event) => setLoginName(event.target.value)}
        />
        <InputField
          id={`${portal}-login-password`}
          label="登录密码"
          name="password"
          type={showPassword ? "text" : "password"}
          value={password}
          placeholder="请输入登录密码"
          autoComplete="current-password"
          icon={<LockKeyhole size={20} />}
          endAction={(
            <button
              type="button"
              aria-label={showPassword ? "隐藏密码" : "显示密码"}
              aria-pressed={showPassword}
              onClick={() => setShowPassword((current) => !current)}
            >
              {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
            </button>
          )}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>

      {error ? <p className="lux-login-card__error" role="alert">{error}</p> : null}

      <button
        className="lux-login-card__submit"
        type="submit"
        disabled={isSubmitting || !loginName.trim() || !password}
      >
        {isSubmitting ? <LoaderCircle className="lux-login-spinner" size={20} /> : null}
        <span>{isSubmitting ? "正在进入..." : "进入工作空间"}</span>
      </button>

      <SecurityBadge>{accessLabel}</SecurityBadge>
    </form>
  );
}
