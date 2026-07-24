import { useState, type FormEvent } from "react";
import { LoaderCircle, LockKeyhole, LogIn, UserRound } from "lucide-react";

import { brandAssets } from "../assets";
import type { LoginRequest } from "../types";


type LoginPageProps = {
  error: string;
  isSubmitting: boolean;
  onSubmit: (credentials: LoginRequest) => Promise<void>;
};


export function LoginPage({ error, isSubmitting, onSubmit }: LoginPageProps) {
  const [loginName, setLoginName] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting || !loginName.trim() || !password) return;
    void onSubmit({
      login_name: loginName.trim(),
      password
    });
  };

  return (
    <main className="login-screen">
      <section className="login-brand" aria-label="KARRIES 禾一斯">
        <div className="login-brand-lockup">
          <img src={brandAssets.monogram} alt="" />
          <div>
            <strong>KARRIES</strong>
            <span>禾一斯</span>
          </div>
        </div>
        <div className="login-brand-copy">
          <p>小红书智能运营工作台</p>
          <h1>让内容创作与矩阵发布更有秩序</h1>
          <span>禾一斯团队专属工作入口</span>
        </div>
        <img className="login-brand-ornament" src={brandAssets.angelMark} alt="" />
      </section>

      <section className="login-panel">
        <form className="login-form" onSubmit={handleSubmit}>
          <header>
            <span className="login-eyebrow">KARRIES WORKSPACE</span>
            <h2>账号登录</h2>
            <p>请输入系统分配的账号和密码</p>
          </header>

          <label className="login-field" htmlFor="login-name">
            <span>登录账号</span>
            <span className="login-input">
              <UserRound aria-hidden="true" size={18} />
              <input
                id="login-name"
                name="login_name"
                type="text"
                value={loginName}
                onChange={(event) => setLoginName(event.target.value)}
                autoComplete="username"
                placeholder="请输入登录账号"
                autoFocus
              />
            </span>
          </label>

          <label className="login-field" htmlFor="login-password">
            <span>登录密码</span>
            <span className="login-input">
              <LockKeyhole aria-hidden="true" size={18} />
              <input
                id="login-password"
                name="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                placeholder="请输入登录密码"
              />
            </span>
          </label>

          {error ? <p className="login-error" role="alert">{error}</p> : null}

          <button
            className="login-submit"
            type="submit"
            disabled={isSubmitting || !loginName.trim() || !password}
          >
            {isSubmitting
              ? <LoaderCircle className="login-spinner" aria-hidden="true" size={18} />
              : <LogIn aria-hidden="true" size={18} />}
            <span>{isSubmitting ? "正在登录..." : "登录工作台"}</span>
          </button>
        </form>
      </section>
    </main>
  );
}
