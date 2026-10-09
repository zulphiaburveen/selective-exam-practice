1. Run supabase_migration.sql in Supabase SQL Editor.
2. Replace pages/Exam.py, pages/Results.py, utils/storage.py.
3. Restart Streamlit.
4. Take a new test attempt with shuffled options, finish, then verify Results/Self Review.
5. Existing attempts have no saved shuffle mapping and use the original order.
6. Review questions continue using original option identities for scoring.
