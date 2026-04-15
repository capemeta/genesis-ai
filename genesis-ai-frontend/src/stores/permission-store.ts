/**
 * 菜单路由状态管理
 * 使用 Zustand 管理用户菜单路由
 * 
 * 职责：
 * - 存储菜单树结构数据
 * - 提供菜单查询方法（路径查找、扁平化等）
 * - 管理菜单加载状态
 * 
 * 注意：
 * - 权限检查逻辑在 auth-store.ts 中，基于 permissions（权限code集合）
 * - 此 store 不做权限判断，仅负责菜单数据结构管理
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { getUserMenus } from '@/lib/api/auth';

export interface MenuItem {
  id: string;
  code: string;
  name: string;
  path?: string;
  type: 'menu' | 'function' | 'directory';
  icon?: string;
  component?: string;
  module?: string;
  sort_order: number;
  children?: MenuItem[];
}

interface MenuStore {
  // 菜单状态
  menus: MenuItem[];
  loading: boolean;
  isLoaded: boolean;
  error: string | null;
  retryCount: number;
  
  // 基础方法
  setMenus: (menus: MenuItem[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  
  // 菜单查询方法（仅负责菜单树结构查询，不做权限判断）
  findMenuByPath: (path: string) => MenuItem | null;
  getFlatMenus: () => MenuItem[];
  getChildMenus: (parentPath: string) => MenuItem[];
  
  // 加载和清除方法
  loadMenus: () => Promise<void>;
  clearMenus: () => void;
}

const MAX_RETRY_COUNT = 3;
const RETRY_DELAY = 1000; // 1秒

export const usePermissionStore = create<MenuStore>()(
  persist(
    (set, get) => ({
      menus: [],
      loading: false,
      isLoaded: false,
      error: null,
      retryCount: 0,
      
      setMenus: (menus) => set({ menus }),
      
      setLoading: (loading) => set({ loading }),
      
      setError: (error) => set({ error }),
      
      // 根据路径查找菜单
      findMenuByPath: (path: string) => {
        const { menus } = get();
        
        if (!path || menus.length === 0) {
          return null;
        }
        
        // 递归查找菜单
        const findMenu = (menuList: MenuItem[]): MenuItem | null => {
          for (const menu of menuList) {
            // 精确匹配
            if (menu.path === path) {
              return menu;
            }
            // 检查子菜单
            if (menu.children && menu.children.length > 0) {
              const found = findMenu(menu.children);
              if (found) {
                return found;
              }
            }
          }
          return null;
        };
        
        return findMenu(menus);
      },
      
      // 获取扁平化菜单列表
      getFlatMenus: () => {
        const { menus } = get();
        
        // 递归扁平化菜单
        const flattenMenus = (menuList: MenuItem[]): MenuItem[] => {
          const result: MenuItem[] = [];
          for (const menu of menuList) {
            result.push(menu);
            if (menu.children && menu.children.length > 0) {
              result.push(...flattenMenus(menu.children));
            }
          }
          return result;
        };
        
        return flattenMenus(menus);
      },
      
      // 获取指定路径的子菜单
      getChildMenus: (parentPath: string) => {
        const { menus } = get();
        
        if (!parentPath || menus.length === 0) {
          return [];
        }
        
        // 查找父菜单
        const parentMenu = get().findMenuByPath(parentPath);
        
        if (!parentMenu || !parentMenu.children) {
          return [];
        }
        
        // 返回子菜单列表（已按 sort_order 排序）
        return [...parentMenu.children].sort((a, b) => a.sort_order - b.sort_order);
      },
      
      // 加载菜单（支持重试）
      loadMenus: async () => {
        const { loading, retryCount } = get();
        
        // 防止重复加载
        if (loading) {
          return;
        }
        
        set({ loading: true, error: null });
        
        try {
          const menusData = await getUserMenus();
          
          set({
            menus: menusData.data || [],
            isLoaded: true,
            loading: false,
            error: null,
            retryCount: 0
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : '加载菜单失败';
          console.error('加载菜单失败:', error);
          
          // 如果未达到最大重试次数，自动重试
          if (retryCount < MAX_RETRY_COUNT) {
            console.log(`将在 ${RETRY_DELAY}ms 后重试 (${retryCount + 1}/${MAX_RETRY_COUNT})`);
            set({
              loading: false,
              error: `${errorMessage}，正在重试...`,
              retryCount: retryCount + 1
            });
            
            // 延迟后重试
            setTimeout(() => {
              get().loadMenus();
            }, RETRY_DELAY);
          } else {
            // 达到最大重试次数，放弃
            set({
              menus: [],
              isLoaded: false,
              loading: false,
              error: errorMessage,
              retryCount: 0
            });
            throw error;
          }
        }
      },
      
      clearMenus: () => set({ 
        menus: [], 
        isLoaded: false, 
        loading: false, 
        error: null,
        retryCount: 0 
      }),
    }),
    {
      name: 'menu-storage',
      // 只持久化菜单，不持久化 loading、error 等状态
      partialize: (state) => ({
        menus: state.menus,
        isLoaded: state.isLoaded,
      }),
    }
  )
);
