import { brandAssets } from "../assets";

type BrandLogoProps = {
  inverse?: boolean;
  subtitle?: string;
};

export function BrandLogo({
  inverse = false,
  subtitle = "小红书智能运营工作台"
}: BrandLogoProps) {
  return (
    <div className={`lux-login-brand-logo${inverse ? " is-inverse" : ""}`}>
      <span className="lux-login-brand-logo__mark">
        <img src={brandAssets.monogram} alt="禾一斯品牌标识" />
      </span>
      <span className="lux-login-brand-logo__text">
        <strong>KARRIES</strong>
        <b>禾一斯</b>
        <small>{subtitle}</small>
      </span>
    </div>
  );
}
