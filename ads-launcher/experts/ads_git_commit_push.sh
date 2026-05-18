cd {{repo_dir}} && git checkout -b {{branch}} && git add -A && git commit -m "{{commit_msg}}" && git push origin {{branch}} 2>&1
echo "EXIT:$?"
