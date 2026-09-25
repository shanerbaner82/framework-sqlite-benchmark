<?php

namespace Nativephp\MobileTrace;

use ReflectionFunction;

/** begin()/end() -> android.os.Trace sections via the bridge; no-ops off-device. */
class Tracer
{
    private ?bool $available = null;

    public function available(): bool
    {
        return $this->available ??= function_exists('nativephp_call')
            && (new ReflectionFunction('nativephp_call'))->isInternal()
            && (! function_exists('nativephp_can') || \nativephp_can('Trace.Begin'));
    }

    public function begin(string $name): void
    {
        if ($this->available()) \nativephp_call('Trace.Begin', json_encode(['n' => $name]));
    }

    public function end(): void
    {
        if ($this->available()) \nativephp_call('Trace.End', '{}');
    }
}
