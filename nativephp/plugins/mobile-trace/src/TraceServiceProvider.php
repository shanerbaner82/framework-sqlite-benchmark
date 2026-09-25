<?php

namespace Nativephp\MobileTrace;

use Illuminate\Support\ServiceProvider;

class TraceServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->singleton(Tracer::class);
    }
}
