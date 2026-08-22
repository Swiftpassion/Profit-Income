import streamlit as st
import pandas as pd
from utils.db_service import get_product_costs, save_product_costs, get_sku_product_names

def render_costs():
    st.subheader("💰 จัดการต้นทุน")
    try:
        cur_data = get_product_costs()
        if cur_data.empty:
            cur_data = pd.DataFrame(columns=['sku', 'unit_cost', 'product_name'])
        for c in ['sku', 'unit_cost', 'product_name']:
            if c not in cur_data.columns:
                cur_data[c] = None

        # ชื่อสินค้าที่แก้ไขเองใน product_costs.product_name มีสิทธิ์เหนือกว่า
        # ถ้ายังไม่เคยแก้ไข จะ fallback ไปใช้ชื่อล่าสุดจากตาราง orders เพื่อใช้ค้นหา/เรียงลำดับ
        try:
            name_map = get_sku_product_names().rename(columns={'product_name': 'product_name_fallback'})
        except Exception:
            name_map = pd.DataFrame(columns=['sku', 'product_name_fallback'])
        display_df = cur_data[['sku', 'unit_cost', 'product_name']].rename(
            columns={'product_name': 'product_name_override'}
        ).merge(name_map, on='sku', how='left')
        has_override = display_df['product_name_override'].astype(str).str.strip().replace('nan', '') != ''
        display_df['product_name'] = display_df['product_name_override'].where(
            has_override, display_df['product_name_fallback']
        )
        display_df['product_name'] = display_df['product_name'].fillna('-')
        display_df = display_df[['sku', 'product_name', 'unit_cost']]

        col_s1, col_s2 = st.columns([3, 2])
        with col_s1:
            search_txt = st.text_input("🔍 ค้นหา ชื่อสินค้า / รหัสสินค้า (SKU)", "", key="cost_search")
        with col_s2:
            sort_opt = st.selectbox(
                "เรียงลำดับ",
                ["ชื่อสินค้า (ก → ฮ)", "ชื่อสินค้า (ฮ → ก)", "SKU (A → Z)", "SKU (Z → A)"],
                key="cost_sort",
            )

        filtered_df = display_df
        if search_txt:
            name_match = filtered_df['product_name'].astype(str).str.contains(search_txt, case=False, na=False)
            sku_match = filtered_df['sku'].astype(str).str.contains(search_txt, case=False, na=False)
            filtered_df = filtered_df[name_match | sku_match]

        if sort_opt == "ชื่อสินค้า (ก → ฮ)":
            filtered_df = filtered_df.sort_values('product_name', ascending=True, kind='stable')
        elif sort_opt == "ชื่อสินค้า (ฮ → ก)":
            filtered_df = filtered_df.sort_values('product_name', ascending=False, kind='stable')
        elif sort_opt == "SKU (A → Z)":
            filtered_df = filtered_df.sort_values('sku', ascending=True, kind='stable')
        elif sort_opt == "SKU (Z → A)":
            filtered_df = filtered_df.sort_values('sku', ascending=False, kind='stable')
        filtered_df = filtered_df.reset_index(drop=True)

        col_c_btn, col_c_info = st.columns([2, 5])
        with col_c_btn:
            save_cost_clicked = st.button("💾 บันทึกต้นทุนสินค้า", type="primary", use_container_width=True)
        with col_c_info:
            st.info("ต้นทุนผูกกับ SKU เท่านั้น (ใช้ร่วมกันทุกแพลตฟอร์ม)")

        # key เปลี่ยนตามการค้นหา/เรียงลำดับ เพื่อให้ editor reset เมื่อผลลัพธ์เปลี่ยน
        editor_key = f"cost_editor_{search_txt}_{sort_opt}"
        edited = st.data_editor(
            filtered_df,
            column_config={
                "sku": st.column_config.TextColumn("รหัสสินค้า (SKU)", required=True),
                "product_name": st.column_config.TextColumn(
                    "ชื่อสินค้า",
                    help="แก้ไขแล้วกด 'บันทึกต้นทุนสินค้า' เพื่ออัพเดทชื่อสินค้าของ SKU นี้ทั้งระบบ",
                ),
                "unit_cost": st.column_config.NumberColumn("ต้นทุน (บาท)", format="%.2f", min_value=0),
            },
            hide_index=True, num_rows="dynamic", use_container_width=True, height=1000,
            key=editor_key,
        )

        if save_cost_clicked and not edited.empty:
            edited = edited.dropna(subset=['sku']).copy()
            edited['sku'] = edited['sku'].astype(str).str.strip().str.upper()
            edited = edited[edited['sku'] != ''].drop_duplicates(subset=['sku'], keep='last')
            # ชื่อที่พิมพ์ในตารางจะถูกปักหมุดเป็นชื่อ SKU นี้ทั้งระบบ; ถ้าเว้นว่าง/เป็น "-" (placeholder) ถือว่าไม่ override
            edited['product_name'] = edited['product_name'].astype(str).str.strip()
            edited.loc[edited['product_name'].isin(['', '-', 'nan', 'None']), 'product_name'] = None
            # รวมแถวที่ถูกกรองซ่อนอยู่กลับเข้าไปก่อนบันทึก (กันข้อมูลนอกผลค้นหาหาย)
            shown_skus = set(filtered_df['sku'].astype(str))
            hidden = cur_data[~cur_data['sku'].astype(str).isin(shown_skus)]
            final = pd.concat(
                [hidden[['sku', 'unit_cost', 'product_name']], edited[['sku', 'unit_cost', 'product_name']]],
                ignore_index=True,
            )
            final = final.drop_duplicates(subset=['sku'], keep='last')
            save_product_costs(final[['sku', 'unit_cost', 'product_name']], replace=True)
            st.cache_data.clear()
            st.success("✅ บันทึกต้นทุนสำเร็จ!")
            st.rerun()
    except Exception as e:
        st.error(f"Error Cost: {e}")
