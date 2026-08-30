/**
 * Why a contract command produced nothing — in the operator's terms, not the project's.
 *
 * One map, two readers: the Project Status page's gap card and the fleet board strip.
 * A class added to the transport layer should land here once, or one surface will say
 * "timed out" while the other says nothing at all.
 */
export const GAP_HINT: Record<string, string> = {
  'not-configured': 'This project publishes no status contract.',
  'command-not-found': 'The configured command is not on this machine.',
  'timeout': 'The project did not answer in time.',
  'spawn-failed': 'The command could not be started.',
  'response-too-large': 'The answer was too large to be a summary.',
  'nonzero-exit': 'The command ran and failed.',
  'invalid-json': 'The answer was not JSON.',
  'invalid-envelope': 'The answer was not in the contract envelope.',
  'missing-version': 'The answer declared no contract version.',
  'unsupported-version': 'The answer uses a contract version this set-core does not read.',
  'project-reported-failure': 'The project answered, and reported a failure.',
  'missing-data': 'The envelope arrived without data.',
}
