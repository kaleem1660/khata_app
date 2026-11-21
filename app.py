








                import io
                tts = gTTS(data, lang="en")
                audio_buffer = io.BytesIO()
                tts.write_to_fp(audio_buffer)
                st.audio(audio_buffer.getvalue(), format="audio/mp3")
            except Exception:
                pass
        elif result_type == "error":
            st.error(data)
        elif result_type == "pending":
            st.markdown("### Review before posting")
            st.warning("Nothing has been posted yet. Check the details carefully.")
            st.markdown(f"**{data['title']}**")
            st.write(data["details"])
            if data.get("warning"):
                st.info(data["warning"])
            st.caption(f"Pending reference: {data['id']} · Expires in {PENDING_MINUTES} minutes")
            with st.form("confirm_command_form"):
                pin = st.text_input("Enter shop PIN to confirm", type="password", max_chars=6)
                confirm = st.form_submit_button("Confirm and post transaction", type="primary")
                if confirm:
                    valid, message = check_pin(pin)
                    if not valid:
                        st.error(message)
                    else:
                        try:
                            post_pending(data["id"])
                            st.success("Transaction posted successfully and saved in the audit log.")
                            st.session_state["command_result"] = None
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
            if st.button("Cancel this pending action"):
                pending = get_pending(data["id"])
                if pending and pending["status"] == "pending":
                    with connect() as conn:
                        conn.execute("UPDATE pending_actions SET status='cancelled' WHERE id=?",
                                     (data["id"],))
                    audit("ACTION_CANCELLED", data["id"])
                st.session_state["command_result"] = None
                st.rerun()

elif page == "Customers & Khata":
    st.subheader("Customers and balances")
    with st.expander("＋ Add new customer", expanded=False):
        with st.form("add_customer_form"):
            customer_name = st.text_input("Customer name")
            phone = st.text_input("Phone (optional)")
            submitted = st.form_submit_button("Add customer")
            if submitted:
                try:
                    add_customer(customer_name, phone)
                    st.success(f"{customer_name} added.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
    customer_rows = []
    for c in get_customers():
        customer_rows.append({
            "Customer":c["name"], "Phone":c["phone"] or "—",
            "Outstanding balance":customer_balance(c["id"])
        })
    st.dataframe(pd.DataFrame(customer_rows), use_container_width=True, hide_index=True)
    st.caption("Outstanding balance is calculated from posted receivable debit and credit entries.")

elif page == "Record Transaction":
    st.subheader("Prepare a transaction")
    st.warning("Transactions are not posted until the shop PIN is verified.")
    tab1, tab2, tab3, tab4 = st.tabs(["Credit sale", "Receive payment", "Cash sale", "In-app payment"])
    customer_options = {c["name"]:c["id"] for c in get_customers()}
    with tab1:
        with st.form("credit_sale_form"):
            name = st.selectbox("Customer", list(customer_options.keys()))
            amount = st.number_input("Credit sale amount (₹)", min_value=1.0, step=100.0)
            go = st.form_submit_button("Prepare credit sale")
            if go:
                cid = customer_options[name]
                action_id = create_pending("credit_sale", {
                    "customer_id":cid, "customer_name":name, "amount":amount
                })
                st.session_state["manual_pending"] = {
                    "id":action_id, "title":"Credit sale",
                    "details":f"{name} · {money(amount)} · New balance: {money(customer_balance(cid)+amount)}"
                }
    with tab2:
        with st.form("payment_form"):
            name2 = st.selectbox("Customer ", list(customer_options.keys()), key="payment_customer")
            amount2 = st.number_input("Payment received (₹)", min_value=1.0, step=100.0, key="payment_amount")
            go2 = st.form_submit_button("Prepare payment")
            if go2:
                cid = customer_options[name2]
                balance = customer_balance(cid)
                if balance <= 0:
                    st.error("This customer has no outstanding balance.")
                elif amount2 > balance:
                    st.error(f"Payment exceeds outstanding balance of {money(balance)}.")
                else:
                    action_id = create_pending("payment_received", {
                        "customer_id":cid, "customer_name":name2, "amount":amount2
                    })
                    st.session_state["manual_pending"] = {
                        "id":action_id, "title":"Payment received",
                        "details":f"From {name2} · {money(amount2)} · Remaining: {money(balance-amount2)}"
                    }
    with tab3:
        with st.form("cash_sale_form"):
            cash_amount = st.number_input("Cash sale amount (₹)", min_value=1.0, step=100.0)
            go3 = st.form_submit_button("Prepare cash sale")
            if go3:
                action_id = create_pending("cash_sale", {"amount":cash_amount})
                st.session_state["manual_pending"] = {
                    "id":action_id, "title":"Cash sale", "details":money(cash_amount)
                }
    with tab4:
        st.caption("Simulated payment request: 1% platform fee is deducted from the gross payment.")
        with st.form("embedded_payment_form"):
            pay_name = st.selectbox("Customer ", list(customer_options.keys()), key="embedded_customer")
            pay_amount = st.number_input("Gross payment amount (₹)", min_value=1.0, step=100.0, key="embedded_amount")
            go4 = st.form_submit_button("Prepare in-app payment settlement")
            if go4:
                cid = customer_options[pay_name]
                balance = customer_balance(cid)
                if balance <= 0:
                    st.error("This customer has no outstanding balance.")
                elif pay_amount > balance:
                    st.error(f"Payment exceeds outstanding balance of {money(balance)}.")
                else:
                    fee = round(pay_amount * 0.01, 2)
                    action_id = create_pending("embedded_payment", {
                        "customer_id":cid, "customer_name":pay_name, "amount":pay_amount
                    })
                    st.session_state["manual_pending"] = {
                        "id":action_id, "title":"In-app payment settlement",
                        "details":f"{pay_name} · Gross: {money(pay_amount)} · Fee: {money(fee)} · Net cash: {money(pay_amount-fee)}"
                    }

    manual = st.session_state.get("manual_pending")
    if manual:
        st.markdown("### Confirm prepared transaction")
        st.write(f"**{manual['title']}** — {manual['details']}")
        with st.form("manual_confirm_form"):
            pin = st.text_input("Shop PIN", type="password", max_chars=6)
            confirm = st.form_submit_button("Confirm and post", type="primary")
            if confirm:
                valid, msg = check_pin(pin)
                if not valid:
                    st.error(msg)
                else:
                    try:
                        post_pending(manual["id"])
                        st.success("Transaction posted.")
                        st.session_state.pop("manual_pending", None)
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

elif page == "Reports":
    st.subheader("Financial reports")
    r1, r2, r3 = st.tabs(["Sales summary", "Receivables ageing", "Trial balance & profit"])
    with r1:




