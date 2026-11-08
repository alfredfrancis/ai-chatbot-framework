// Imported first by main.tsx: Zod decides when a schema is created whether to compile its validator with
// new Function(), which the app's Content-Security-Policy forbids. OpenUI creates schemas at import time.
import { z } from "zod/v4";

z.config({ jitless: true });
