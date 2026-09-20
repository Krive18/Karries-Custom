export type Portal = "customer" | "manager" | "developer";


const tokenKeys: Record<Portal, string> = {
  customer: "karries_customer_access_token",
  manager: "karries_manager_access_token",
  developer: "karries_developer_access_token"
};


export function tokenKey(portal: Portal) {
  return tokenKeys[portal];
}


export function getPortalToken(portal: Portal) {
  return window.localStorage.getItem(tokenKey(portal));
}


export function setPortalToken(portal: Portal, token: string) {
  window.localStorage.setItem(tokenKey(portal), token);
}


export function clearPortalToken(portal: Portal) {
  window.localStorage.removeItem(tokenKey(portal));
}
