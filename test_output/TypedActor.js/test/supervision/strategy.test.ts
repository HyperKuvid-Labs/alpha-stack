import { describe, it, expect, spyOn, beforeEach, afterEach } from 'bun:test';
import { SupervisionStrategy, Supervisor, Decider } from '../../src/supervision/strategy';

describe('SupervisionStrategy', () => {
	it('should define four unique symbol strategies', () => {
		expect(SupervisionStrategy.Restart).toBeTypeOf('symbol');
		expect(SupervisionStrategy.Resume).toBeTypeOf('symbol');
		expect(SupervisionStrategy.Stop).toBeTypeOf('symbol');
		expect(SupervisionStrategy.Escalate).toBeTypeOf('symbol');

		const strategies = Object.values(SupervisionStrategy);
		const uniqueStrategies = new Set(strategies);

		expect(strategies.length).toBe(4);
		expect(uniqueStrategies.size).toBe(4);
	});
});

describe('Supervisor', () => {
	describe('constructor', () => {
		it('should create a Supervisor instance with a valid decider function', () => {
			const decider: Decider = () => SupervisionStrategy.Restart;
			const supervisor = new Supervisor(decider);
			expect(supervisor).toBeInstanceOf(Supervisor);
			expect(supervisor.decider).toBe(decider);
		});

		it('should throw a TypeError if the decider is not a function', () => {
			expect(() => new Supervisor(null as any)).toThrow('Supervisor decider must be a function.');
			expect(() => new Supervisor(undefined as any)).toThrow('Supervisor decider must be a function.');
			expect(() => new Supervisor({} as any)).toThrow('Supervisor decider must be a function.');
			expect(() => new Supervisor('string' as any)).toThrow('Supervisor decider must be a function.');
		});
	});

	describe('handleFailure', () => {
		const testError = new Error('Test failure');

		it('should call the decider with the provided error', () => {
			const decider = (err: Error): any => {
				expect(err).toBe(testError);
				return SupervisionStrategy.Restart;
			};
			const deciderSpy = spyOn({ decider }, 'decider');
			const supervisor = new Supervisor(deciderSpy);

			supervisor.handleFailure(testError);
			expect(deciderSpy).toHaveBeenCalledTimes(1);
			expect(deciderSpy).toHaveBeenCalledWith(testError);
		});

		it('should return SupervisionStrategy.Restart when decider returns Restart', () => {
			const decider: Decider = () => SupervisionStrategy.Restart;
			const supervisor = new Supervisor(decider);
			const decision = supervisor.handleFailure(testError);
			expect(decision).toBe(SupervisionStrategy.Restart);
		});

		it('should return SupervisionStrategy.Resume when decider returns Resume', () => {
			const decider: Decider = () => SupervisionStrategy.Resume;
			const supervisor = new Supervisor(decider);
			const decision = supervisor.handleFailure(testError);
			expect(decision).toBe(SupervisionStrategy.Resume);
		});

		it('should return SupervisionStrategy.Stop when decider returns Stop', () => {
			const decider: Decider = () => SupervisionStrategy.Stop;
			const supervisor = new Supervisor(decider);
			const decision = supervisor.handleFailure(testError);
			expect(decision).toBe(SupervisionStrategy.Stop);
		});

		it('should return SupervisionStrategy.Escalate when decider returns Escalate', () => {
			const decider: Decider = () => SupervisionStrategy.Escalate;
			const supervisor = new Supervisor(decider);
			const decision = supervisor.handleFailure(testError);
			expect(decision).toBe(SupervisionStrategy.Escalate);
		});

		describe('error handling within decider', () => {
			let consoleErrorSpy: any;

			beforeEach(() => {
				consoleErrorSpy = spyOn(console, 'error').mockImplementation(() => {});
			});

			afterEach(() => {
				consoleErrorSpy.mockRestore();
			});

			it('should return SupervisionStrategy.Escalate if the decider function throws an error', () => {
				const deciderError = new Error('Decider exploded');
				const decider: Decider = () => {
					throw deciderError;
				};
				const supervisor = new Supervisor(decider);
				const decision = supervisor.handleFailure(testError);

				expect(decision).toBe(SupervisionStrategy.Escalate);
				expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
				expect(consoleErrorSpy).toHaveBeenCalledWith(
					'An error occurred within the supervisor decider function itself. Escalating failure.',
					deciderError
				);
			});

			it('should return SupervisionStrategy.Escalate if the decider returns an invalid symbol value', () => {
				const invalidStrategy = Symbol('InvalidStrategy');
				const decider = () => invalidStrategy as any;
				const supervisor = new Supervisor(decider);
				const decision = supervisor.handleFailure(testError);

				expect(decision).toBe(SupervisionStrategy.Escalate);
				expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
				expect(consoleErrorSpy).toHaveBeenCalledWith(
					'Decider function returned an invalid supervision strategy. Escalating failure.'
				);
			});

			it('should return SupervisionStrategy.Escalate if the decider returns a non-symbol value', () => {
				const decider = () => 'not a symbol' as any;
				const supervisor = new Supervisor(decider);
				const decision = supervisor.handleFailure(testError);

				expect(decision).toBe(SupervisionStrategy.Escalate);
				expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
			});
		});
	});
});
