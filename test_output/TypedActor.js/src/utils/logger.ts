export const Logger = {
  info(message: string): void {
    const timestamp = new Date().toISOString();
    console.info(`[${timestamp}] [INFO] ${message}`);
  },

  warn(message: string): void {
    const timestamp = new Date().toISOString();
    console.warn(`[${timestamp}] [WARN] ${message}`);
  },

  error(message: string): void {
    const timestamp = new Date().toISOString();
    console.error(`[${timestamp}] [ERROR] ${message}`);
  },
};
