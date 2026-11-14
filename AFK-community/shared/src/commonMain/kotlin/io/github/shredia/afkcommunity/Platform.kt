package io.github.shredia.afkcommunity

interface Platform {
    val name: String
}

expect fun getPlatform(): Platform