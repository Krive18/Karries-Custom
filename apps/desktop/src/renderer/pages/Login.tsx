import { brandAssets } from "../assets";
import type { Portal } from "../auth/portalSession";
import { AngelHero } from "../components/AngelHero";
import { BeianFooter } from "../components/BeianFooter";
import { DeveloperLoginHero } from "../components/DeveloperLoginHero";
import { LoginCard } from "../components/LoginCard";
import type { LoginRequest } from "../types";
import "../styles/login.css";
import "../styles/developer-login.css";

export type PortalLoginPageProps = {
  portal: Portal;
  error: string;
  isSubmitting: boolean;
  onSubmit: (credentials: LoginRequest) => Promise<void>;
};

type PortalCopy = {
  eyebrow: string;
  title: string;
  product: string;
  description: string;
  brandTitle: string;
  brandAccent: string;
  brandSubtitle: string;
  accessLabel: string;
};

const portalCopy: Record<Portal, PortalCopy> = {
  customer: {
    eyebrow: "KARRIES WORKSPACE",
    title: "账号登录",
    product: "小红书智能运营工作台",
    description: "欢迎回来，开启高效的内容运营",
    brandTitle: "让内容生产与矩阵发布",
    brandAccent: "更有秩序",
    brandSubtitle: "统一管理创作、审核、账号与定时发布",
    accessLabel: "员工专属工作空间"
  },
  manager: {
    eyebrow: "KARRIES MANAGEMENT",
    title: "管理端登录",
    product: "禾一斯运营管理中心",
    description: "查看团队、内容与矩阵发布全貌",
    brandTitle: "让团队运营更清晰",
    brandAccent: "让管理决策更从容",
    brandSubtitle: "成员、账号矩阵、内容与发布进度统一管理",
    accessLabel: "禾一斯负责人专属入口"
  },
  developer: {
    eyebrow: "KARRIES INTERNAL",
    title: "内部系统登录",
    product: "点绘环球技术运营中心",
    description: "内部管理员安全访问入口",
    brandTitle: "让服务响应更有序",
    brandAccent: "让技术交付更高效",
    brandSubtitle: "仅限点绘环球内部人员使用",
    accessLabel: "内部安全访问"
  }
};

export function Login({ portal, error, isSubmitting, onSubmit }: PortalLoginPageProps) {
  const copy = portalCopy[portal];

  return (
    <main className={`lux-login-page lux-login-page--${portal}`}>
      {portal === "developer" ? (
        <DeveloperLoginHero />
      ) : (
        <AngelHero
          product={copy.product}
          title={copy.brandTitle}
          accent={copy.brandAccent}
          subtitle={copy.brandSubtitle}
        />
      )}
      <section className="lux-login-access" aria-label={`${copy.title}区域`}>
        <img
          className="lux-login-access__motif"
          src={brandAssets.angelMark}
          alt=""
          aria-hidden="true"
        />
        <LoginCard
          portal={portal}
          eyebrow={copy.eyebrow}
          title={copy.title}
          description={copy.description}
          accessLabel={copy.accessLabel}
          error={error}
          isSubmitting={isSubmitting}
          onSubmit={onSubmit}
        />
      </section>
      {portal === "customer" ? <BeianFooter /> : null}
    </main>
  );
}
