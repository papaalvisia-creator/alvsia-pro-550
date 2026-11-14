package com.alvsia.pro.tool

/**
 * The single navigation-to-provider boundary for ALVSIA Unified Engine.
 *
 * The UI exposes only seven Smart menus and twenty submenu groups. Each
 * selected workspace action carries its stable legacy provider ID; this
 * facade validates the menu/provider relationship before ToolEngine executes
 * the operation through the shared bridge.
 */
data class UnifiedEngineRoute(
    val visibleMenuId: Int,
    val providerModuleId: Int,
    val operationId: String,
    val operationTitle: String
)

object UnifiedEngineFacade {
    private val providersByMenu: Map<Int, Set<Int>> = mapOf(
        1 to setOf(5, 15, 16, 18),
        2 to setOf(1, 2, 3, 14),
        3 to setOf(4),
        4 to setOf(6, 12, 13),
        5 to setOf(10, 11, 17, 20),
        6 to setOf(7, 8, 9),
        7 to setOf(19)
    )

    fun resolve(visibleMenuId: Int, action: SubTool): UnifiedEngineRoute {
        require(visibleMenuId in 1..7) {
            "Unknown visible Smart menu: $visibleMenuId"
        }
        val providerId = action.legacyModuleId
            ?: SmartModuleRouter.backendModule(visibleMenuId, action.id)
        require(providerId in providersByMenu.getValue(visibleMenuId)) {
            "Provider $providerId is not registered under visible menu $visibleMenuId"
        }
        require(action.id.isNotBlank()) { "Operation ID must not be blank" }

        return UnifiedEngineRoute(
            visibleMenuId = visibleMenuId,
            providerModuleId = providerId,
            operationId = SmartModuleRouter.normalizedSubId(visibleMenuId, action.id),
            operationTitle = action.title
        )
    }

    fun visibleMenuCount(): Int = providersByMenu.size

    fun legacyProviderIds(): Set<Int> = providersByMenu.values.flatten().toSet()
}
