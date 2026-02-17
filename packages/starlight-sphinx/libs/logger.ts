import type { AstroIntegrationLogger } from 'astro'

export function createLogger(logger: AstroIntegrationLogger) {
  return {
    error(message: string) {
      logger.error(message)
    },
    warn(message: string) {
      logger.warn(message)
    },
    info(message: string) {
      logger.info(message)
    },
    debug(message: string) {
      logger.debug(message)
    },
  }
}
