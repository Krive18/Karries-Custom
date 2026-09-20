import { ShieldCheck } from "lucide-react";
import type { PointerEvent } from "react";

import { brandAssets } from "../assets";
import { BrandLogo } from "./BrandLogo";

type AngelHeroProps = {
  product: string;
  title: string;
  accent: string;
  subtitle: string;
};

export function AngelHero({ product, title, accent, subtitle }: AngelHeroProps) {
  const handlePointerMove = (event: PointerEvent<HTMLElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) / bounds.width - 0.5) * 10;
    const y = ((event.clientY - bounds.top) / bounds.height - 0.5) * 8;
    event.currentTarget.style.setProperty("--lux-parallax-x", `${x}px`);
    event.currentTarget.style.setProperty("--lux-parallax-y", `${y}px`);
  };

  const resetPointerPosition = (event: PointerEvent<HTMLElement>) => {
    event.currentTarget.style.setProperty("--lux-parallax-x", "0px");
    event.currentTarget.style.setProperty("--lux-parallax-y", "0px");
  };

  return (
    <section
      className="lux-login-hero"
      aria-label={product}
      onPointerMove={handlePointerMove}
      onPointerLeave={resetPointerPosition}
    >
      <div className="lux-login-hero__light" aria-hidden="true" />
      <div className="lux-login-hero__parallax">
        <div className="lux-login-hero__reveal">
          <img
            className="lux-login-hero__art"
            src={brandAssets.angelHero}
            alt="禾一斯天使品牌主视觉"
          />
        </div>
      </div>

      <header className="lux-login-hero__brand">
        <BrandLogo inverse subtitle={product} />
      </header>

      <div className="lux-login-hero__copy">
        <p>{product}</p>
        <h1>
          <span>{title}</span>
          <em>{accent}</em>
        </h1>
        <i aria-hidden="true" />
        <strong>{subtitle}</strong>
      </div>

      <div className="lux-login-hero__security">
        <ShieldCheck size={15} aria-hidden="true" />
        <span>安全访问 · 账号由管理员统一开通</span>
      </div>
    </section>
  );
}
