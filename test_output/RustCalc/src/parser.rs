use std::iter::Peekable;
use std::str::Chars;

pub struct ParseError {
    pub kind: String,
    pub message: String,
}

#[derive(Clone, PartialEq)]
enum Token {
    Number(f64),
    Plus,
    Minus,
    Star,
    Slash,
    LParen,
    RParen,
}

pub fn evaluate(input: String) -> Result<f64, ParseError> {
    let tokens = tokenize(&input)?;
    let mut parser = Parser::new(tokens);
    let result = parser.parse_expression()?;
    if parser.pos < parser.tokens.len() {
        return Err(ParseError {
            kind: "SyntaxError".to_string(),
            message: "Unexpected input at end of expression".to_string(),
        });
    }
    Ok(result)
}

fn tokenize(input: &str) -> Result<Vec<Token>, ParseError> {
    let mut tokens = Vec::new();
    let mut chars = input.chars().peekable();

    while let Some(&c) = chars.peek() {
        match c {
            '0'..='9' | '.' => {
                let mut num_str = String::new();
                let mut has_dot = false;
                while let Some(&nc) = chars.peek() {
                    if nc == '.' {
                        if has_dot {
                            return Err(ParseError {
                                kind: "InvalidToken".to_string(),
                                message: "Invalid number format".to_string(),
                            });
                        }
                        has_dot = true;
                    } else if !nc.is_ascii_digit() && nc != '.' {
                        break;
                    }
                    num_str.push(chars.next().unwrap());
                }
                match num_str.parse::<f64>() {
                    Ok(n) => tokens.push(Token::Number(n)),
                    Err(_) => {
                        return Err(ParseError {
                            kind: "InvalidToken".to_string(),
                            message: format!("Could not parse number: {}", num_str),
                        })
                    }
                }
            }
            '+' => {
                tokens.push(Token::Plus);
                chars.next();
            }
            '-' => {
                tokens.push(Token::Minus);
                chars.next();
            }
            '*' => {
                tokens.push(Token::Star);
                chars.next();
            }
            '/' => {
                tokens.push(Token::Slash);
                chars.next();
            }
            '(' => {
                tokens.push(Token::LParen);
                chars.next();
            }
            ')' => {
                tokens.push(Token::RParen);
                chars.next();
            }
            ' ' | '\t' | '\n' | '\r' => {
                chars.next();
            }
            _ => {
                return Err(ParseError {
                    kind: "InvalidCharacter".to_string(),
                    message: format!("Unrecognized character: {}", c),
                })
            }
        }
    }
    Ok(tokens)
}

struct Parser {
    tokens: Vec<Token>,
    pos: usize,
}

impl Parser {
    fn new(tokens: Vec<Token>) -> Self {
        Parser { tokens, pos: 0 }
    }

    fn peek(&self) -> Option<&Token> {
        self.tokens.get(self.pos)
    }

    fn consume(&mut self) -> Option<Token> {
        let token = self.tokens.get(self.pos).cloned();
        self.pos += 1;
        token
    }

    fn parse_expression(&mut self) -> Result<f64, ParseError> {
        let mut left = self.parse_term()?;

        while let Some(token) = self.peek() {
            match token {
                Token::Plus => {
                    self.consume();
                    let right = self.parse_term()?;
                    left += right;
                }
                Token::Minus => {
                    self.consume();
                    let right = self.parse_term()?;
                    left -= right;
                }
                _ => break,
            }
        }

        Ok(left)
    }

    fn parse_term(&mut self) -> Result<f64, ParseError> {
        let mut left = self.parse_factor()?;

        while let Some(token) = self.peek() {
            match token {
                Token::Star => {
                    self.consume();
                    let right = self.parse_factor()?;
                    left *= right;
                }
                Token::Slash => {
                    self.consume();
                    let right = self.parse_factor()?;
                    if right == 0.0 {
                        return Err(ParseError {
                            kind: "DivisionByZero".to_string(),
                            message: "Attempted to divide by zero".to_string(),
                        });
                    }
                    left /= right;
                }
                _ => break,
            }
        }

        Ok(left)
    }

    fn parse_factor(&mut self) -> Result<f64, ParseError> {
        match self.peek() {
            Some(Token::Plus) => {
                self.consume();
                self.parse_factor()
            }
            Some(Token::Minus) => {
                self.consume();
                let val = self.parse_factor()?;
                Ok(-val)
            }
            Some(Token::LParen) => {
                self.consume();
                let expr = self.parse_expression()?;
                match self.peek() {
                    Some(Token::RParen) => {
                        self.consume();
                        Ok(expr)
                    }
                    _ => Err(ParseError {
                        kind: "SyntaxError".to_string(),
                        message: "Mismatched parentheses: expected ')'".to_string(),
                    }),
                }
            }
            Some(Token::Number(n)) => {
                self.consume();
                Ok(*n)
            }
            _ => Err(ParseError {
                kind: "SyntaxError".to_string(),
                message: "Unexpected token, expected number, parenthesis, or operator".to_string(),
            }),
        }
    }
}
