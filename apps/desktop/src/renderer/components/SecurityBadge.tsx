import { ShieldCheck } from "lucide-react";

type SecurityBadgeProps = {
  children: string;
};

export function SecurityBadge({ children }: SecurityBadgeProps) {
  return (
    <p className="lux-login-security-badge">
      <ShieldCheck size={16} aria-hidden="true" />
      <span>{children}</span>
    </p>
  );
}
