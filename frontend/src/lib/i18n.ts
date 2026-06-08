import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import admin from "@/locales/en/admin.json";
import auth from "@/locales/en/auth.json";
import common from "@/locales/en/common.json";
import driver from "@/locales/en/driver.json";
import parent from "@/locales/en/parent.json";

export const NAMESPACES = ["common", "auth", "parent", "driver", "admin"] as const;

export const resources = {
  en: { common, auth, parent, driver, admin },
} as const;

void i18n.use(initReactI18next).init({
  resources,
  lng: "en",
  fallbackLng: "en",
  ns: [...NAMESPACES],
  defaultNS: "common",
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;
