import { useEffect, useState } from "react";

import { managerApi } from "../api/managerClient";
import type { AdminEmployeeView } from "../types";

type ManagerEmployeeSelectProps = {
  value: string;
  onChange: (value: string) => void;
};

export function ManagerEmployeeSelect({
  value,
  onChange
}: ManagerEmployeeSelectProps) {
  const [employees, setEmployees] = useState<AdminEmployeeView[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    managerApi
      .listEmployees(new URLSearchParams({ page: "1", page_size: "100" }))
      .then((result) => {
        if (!active) return;
        setEmployees(result.items);
        setFailed(false);
      })
      .catch(() => {
        if (!active) return;
        setEmployees([]);
        setFailed(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <label>
      员工
      <select
        aria-label="员工"
        value={value}
        disabled={loading || failed}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">
          {loading ? "正在加载员工..." : failed ? "员工列表加载失败" : "全部员工"}
        </option>
        {employees.map((employee) => (
          <option key={employee.id} value={employee.id}>
            {employee.nickname}（{employee.login_name}）
            {employee.status === 2 ? " · 已停用" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
